from pipeline.classification import process as process_classification
from pipeline.extraction_3.processor import process as process_extraction
from pipeline.ocr_2 import process as process_ocr
from pipeline.text_1 import process as process_text
from invoices.repository import InvoiceDetails
from shared.storage import download_file
from pipeline.erp import bind_snapshot


def run_pipeline(invoice_record: InvoiceDetails) -> None:
    bind_snapshot(invoice_record)
    records = {record.stage: record for record in invoice_record.stages}
    if any(records[stage].status != "ready" for stage in ("text", "ocr")):
        pdf = download_file(f"{invoice_record.id}/original.pdf")
        if records["text"].status != "ready":
            process_text(pdf, invoice_record)
        if records["ocr"].status != "ready":
            process_ocr(pdf, invoice_record)
    if records["extraction"].status != "ready":
        process_extraction(invoice_record)
    process_classification(invoice_record)
