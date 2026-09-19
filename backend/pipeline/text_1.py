import subprocess

from invoices.repository import Invoice
from invoices.stages import stage_attempt
from shared.logger import get_logger
from shared.storage import upload_file

logger = get_logger()


def extract_text(pdf_bytes: bytes) -> str:
    """Read the PDF's native text layer while preserving its layout."""
    result = subprocess.run(
        ["pdftotext", "-layout", "-", "-"],
        input=pdf_bytes, capture_output=True, check=True,
    )
    text = result.stdout.decode("utf-8")
    logger.info("[TEXT] Extracted %s characters from the PDF text layer", len(text))
    return text


def process(pdf_bytes: bytes, invoice_record: Invoice) -> None:
    result_path = f"{invoice_record.id}/native.txt"
    with stage_attempt(invoice_record.id, invoice_record.name, "text", result_path):
        text = extract_text(pdf_bytes)
        upload_file(result_path, text.encode("utf-8"), "text/plain; charset=utf-8")
