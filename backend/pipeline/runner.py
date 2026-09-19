from pipeline.extraction_3.processor import process as process_extraction
from pipeline.ocr_2 import process as process_ocr
from pipeline.text_1 import process as process_text
from documents.repository import DocumentDetails
from shared.storage import download_file
from pipeline.erp import bind_snapshot


def run_pipeline(document: DocumentDetails) -> None:
    bind_snapshot(document)
    records = {record.stage: record for record in document.stages}
    if any(records[stage].status != "ready" for stage in ("text", "ocr")):
        pdf = download_file(f"{document.id}/original.pdf")
        if records["text"].status != "ready":
            process_text(pdf, document)
        if records["ocr"].status != "ready":
            process_ocr(pdf, document)
    if records["extraction"].status != "ready":
        process_extraction(document)
