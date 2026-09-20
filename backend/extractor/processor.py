import json
import time
from hashlib import sha256

from invoices.repository import InvoiceDetails, save_invoice_extraction, write_invoice
from invoices.erp import bind_snapshot, match_entry
from invoices.repository import start_extraction, finish_extraction, fail_extraction
from extractor.text import extract_text
from extractor.extraction import extract_invoice
from extractor.categories import CategorizedInvoiceExtraction, MODEL as CATEGORY_MODEL, categorize_invoice
from extractor.pages import render_pages
from extractor.verifactu import detect_verifactu
from extractor.extractor import MODEL
from extractor.recovery import recover_identifiers
from suppliers.repository import list_suppliers
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
        verifactu = detect_verifactu(pages)
        logger.info('[EXTRACTION] Veri*Factu QR for %s: %s', document.name,
                    'not detected' if verifactu is None else f'{verifactu.environment}, page {verifactu.page}')
        document.pages = len(pages)
        write_invoice(document)
        for number, image in enumerate(pages, start=1):
            upload_file(f"{prefix}/pages/page-{number}.jpg", image, "image/jpeg")
        logger.info("[EXTRACTION] Extracting invoice fields from native text and %s page images for %s", len(pages), document.name)
        with track_usage("openrouter", MODEL, "extraction", str(document.id), document.name) as extraction_usage:
            extraction = extract_invoice(native.decode("utf-8"), pages, usage=extraction_usage)
        extraction, corrections = recover_identifiers(extraction, list_suppliers())
        if extraction.line_items:
            with track_usage("typesafe", CATEGORY_MODEL, "categorization", str(document.id), document.name) as usage:
                extraction = categorize_invoice(extraction, usage)
        else:
            extraction = CategorizedInvoiceExtraction.model_validate(extraction.model_dump())
        for correction in corrections:
            logger.info("[EXTRACTION] Recovered %s for %s using supplier %s and exact %s: %s -> %s",
                        correction.field, document.name, correction.supplier_id, correction.matched_field,
                        correction.original, correction.corrected)
        content = extraction.model_dump_json(indent=2).encode("utf-8")
        metadata = {
            "verifactu": None if verifactu is None else verifactu.model_dump(),
            "native_sha256": sha256(native).hexdigest(),
            "pdf_sha256": sha256(pdf).hexdigest(),
            "page_sha256": [sha256(page).hexdigest() for page in pages],
            "features_sha256": sha256(content).hexdigest(),
            "model": extraction_usage.model,
            "categorization_model": CATEGORY_MODEL,
            "identifier_corrections": [correction.model_dump() for correction in corrections],
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
