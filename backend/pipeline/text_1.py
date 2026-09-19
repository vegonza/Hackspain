import subprocess

from documents.repository import Document
from documents.stages import stage_attempt
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


def process(pdf_bytes: bytes, document: Document) -> None:
    result_path = f"{document.id}/native.txt"
    with stage_attempt(document.id, document.name, "text", result_path):
        text = extract_text(pdf_bytes)
        upload_file(result_path, text.encode("utf-8"), "text/plain; charset=utf-8")
