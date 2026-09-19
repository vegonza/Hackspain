import json
import time
from hashlib import sha256

from invoices.repository import InvoiceDetails, save_invoice_extraction, write_invoice
from invoices.erp import bind_snapshot, match_entry
from invoices.repository import start_extraction, finish_extraction, fail_extraction
from extractor.text import extract_text
from extractor.extraction import extract_invoice
from extractor.pages import render_pages
from extractor.extractor import MODEL
from shared.logger import get_logger
from shared.storage import download_file, upload_file
from shared.usage import track_usage

logger = get_logger()


def process(document: InvoiceDetails) -> None:
    prefix = f"{document.id}/extraction"
    result_path = f"{prefix}/features.json"
    start_extraction(document.id, document.name)
    started = time.perf_counter()
    try:
        bind_snapshot(document)
        pdf = download_file(f"{document.id}/original.pdf")
        native = extract_text(pdf).encode("utf-8")
        upload_file(f"{document.id}/native.txt", native, "text/plain; charset=utf-8")
        pages = render_pages(pdf)
        document.pages = len(pages)
        write_invoice(document)
        for number, image in enumerate(pages, start=1):
            upload_file(f"{prefix}/pages/page-{number}.jpg", image, "image/jpeg")
        logger.info("[EXTRACTION] Extracting invoice fields from native text and %s page images for %s", len(pages), document.name)
        with track_usage("openrouter", MODEL, "extraction", str(document.id), document.name) as usage:
            extraction = extract_invoice(native.decode("utf-8"), pages, usage=usage)
        content = extraction.model_dump_json(indent=2).encode("utf-8")
        metadata = {
            "native_sha256": sha256(native).hexdigest(),
            "pdf_sha256": sha256(pdf).hexdigest(),
            "page_sha256": [sha256(page).hexdigest() for page in pages],
            "features_sha256": sha256(content).hexdigest(),
            "model": MODEL,
        }
        upload_file(f"{prefix}/extraction.json", json.dumps(metadata).encode("utf-8"), "application/json")
        upload_file(result_path, content, "application/json")
        save_invoice_extraction(document.id, document.name, extraction)
        match_entry(document, extraction.purchase_order)
        logger.info("[EXTRACTION] Saved %s: %s line items, %s uncertainties",
                    document.name, len(extraction.line_items), len(extraction.uncertainties))
        finish_extraction(document.id, document.name, round((time.perf_counter() - started) * 1000), result_path)
        document.result_path = result_path
    except Exception:
        try:
            fail_extraction(document.id, document.name, round((time.perf_counter() - started) * 1000))
        except Exception:
            logger.exception("[EXTRACTION] Could not save failed attempt for %s", document.name)
        raise
