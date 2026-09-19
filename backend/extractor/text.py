import subprocess

from shared.logger import get_logger

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
