import base64
import os
from pathlib import Path

from mistralai.client import Mistral
from shared.logger import get_logger

logger = get_logger()
OCR_MODEL = "mistral-ocr-latest"
OCR_TIMEOUT_MS = 180_000
MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]


def extract_markdown(pdf_bytes: bytes, directory: Path) -> tuple[str, int]:
    """Extract page Markdown with Mistral OCR and save its images locally."""
    if not MISTRAL_API_KEY.strip():
        raise ValueError("MISTRAL_API_KEY is empty")

    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    with Mistral(api_key=MISTRAL_API_KEY, timeout_ms=OCR_TIMEOUT_MS) as client:
        response = client.ocr.process(
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{encoded}",
            },
            model=OCR_MODEL,
            include_image_base64=True,
        )

    pages: list[str] = []
    for page in response.pages:
        markdown = page.markdown
        for index, image in enumerate(page.images):
            if image.image_base64 is None:
                raise ValueError("OCR image data is missing")
            encoded_image = image.image_base64.split(",")[-1]
            filename = f"page-{page.index}-image-{index}.jpg"
            (directory / filename).write_bytes(base64.b64decode(encoded_image))
            markdown = markdown.replace(f"]({image.id})", f"](/api/documents/{directory.name}/images/{filename})")
        pages.append(markdown)

    if not pages:
        raise ValueError("OCR returned no pages")
    logger.info("[OCR] Extracted %s pages using %s", len(pages), OCR_MODEL)
    return "\n\n".join(pages), len(pages)
