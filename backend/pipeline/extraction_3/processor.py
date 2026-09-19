import json
from hashlib import sha256

from invoices.repository import InvoiceDetails, save_invoice_extraction
from pipeline.erp import match_entry
from invoices.stages import stage_attempt
from pipeline.extraction_3.extraction import extract_invoice
from pipeline.extraction_3.pages import render_pages
from pipeline.extraction_3.extractor import MODEL
from shared.logger import get_logger
from shared.storage import download_file, upload_file
from shared.usage import track_usage

logger = get_logger()


def process(invoice_record: InvoiceDetails) -> None:
    prefix = f"{invoice_record.id}/extraction"
    result_path = f"{prefix}/features.json"
    with stage_attempt(invoice_record.id, invoice_record.name, "extraction", result_path):
        native = download_file(f"{invoice_record.id}/native.txt")
        markdown = download_file(f"{invoice_record.id}/document.md")
        pdf = download_file(f"{invoice_record.id}/original.pdf")
        pages = render_pages(pdf)
        for number, image in enumerate(pages, start=1):
            upload_file(f"{prefix}/pages/page-{number}.jpg", image, "image/jpeg")
        logger.info("[EXTRACTION] Extracting invoice fields from native text, OCR and %s page images for %s", len(pages), invoice_record.name)
        with track_usage("openrouter", MODEL, "extraction", str(invoice_record.id), invoice_record.name) as usage:
            extraction = extract_invoice(native.decode("utf-8"), markdown.decode("utf-8"), pages, usage=usage)
        content = extraction.model_dump_json(indent=2).encode("utf-8")
        metadata = {
            "native_sha256": sha256(native).hexdigest(),
            "ocr_sha256": sha256(markdown).hexdigest(),
            "pdf_sha256": sha256(pdf).hexdigest(),
            "page_sha256": [sha256(page).hexdigest() for page in pages],
            "features_sha256": sha256(content).hexdigest(),
            "model": MODEL,
        }
        upload_file(f"{prefix}/extraction.json", json.dumps(metadata).encode("utf-8"), "application/json")
        upload_file(result_path, content, "application/json")
        save_invoice_extraction(invoice_record.id, invoice_record.name, extraction)
        match_entry(invoice_record, extraction.purchase_order)
        logger.info("[EXTRACTION] Saved %s: %s line items, %s uncertainties",
                    invoice_record.name, len(extraction.line_items), len(extraction.uncertainties))
