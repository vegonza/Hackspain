import base64
import os
import json
from decimal import Decimal
from pathlib import Path

from mistralai.client import Mistral
from mistralai.client.models import OCRResponse
from documents.repository import Document, write_document
from documents.stages import stage_attempt
from shared.logger import get_logger
from shared.storage import upload_file
from shared.usage import USAGE_OUTBOX, UsageEntry, track_usage
from shared.redis import get_redis

logger = get_logger()
OCR_MODEL = "mistral-ocr-latest"
OCR_TIMEOUT_MS = 180_000
OCR_COST_PER_PAGE = Decimal("0.004")


def extract_markdown(pdf_bytes: bytes, document_id: str, document_name: str) -> tuple[str, int]:
    """Extract page Markdown with Mistral OCR and store images in the private bucket."""
    if not os.environ["MISTRAL_API_KEY"].strip():
        raise ValueError("MISTRAL_API_KEY is empty")

    checkpoint_key = f"documents:ocr:{document_id}"
    with get_redis() as redis:
        checkpoint = redis.get(checkpoint_key)
    if checkpoint is not None:
        saved = json.loads(checkpoint)
        response = OCRResponse.model_validate(saved["response"])
        with get_redis() as redis:
            redis.hset(USAGE_OUTBOX, saved["usage"]["id"], json.dumps(saved["usage"]))
    else:
        response = request_ocr(pdf_bytes, document_id, document_name, checkpoint_key)

    upload_file(f"{document_id}/ocr.json", response.model_dump_json().encode("utf-8"), "application/json")
    pages: list[str] = []
    for page in response.pages:
        markdown = page.markdown
        for index, image in enumerate(page.images):
            if image.image_base64 is None:
                raise ValueError("OCR image data is missing")
            encoded_image = image.image_base64.split(",")[-1]
            filename = f"page-{page.index}-image-{index}.jpg"
            upload_file(f"{document_id}/{filename}", base64.b64decode(encoded_image), "image/jpeg")
            markdown = markdown.replace(f"]({image.id})", f"](/api/documents/{document_id}/images/{filename})")
        pages.append(markdown)

    if not pages:
        raise ValueError("OCR returned no pages")
    logger.info("[OCR] Extracted %s pages using %s", len(pages), OCR_MODEL)
    markdown = "\n\n".join(pages)
    upload_file(f"{document_id}/document.md", markdown.encode("utf-8"), "text/markdown; charset=utf-8")
    return markdown, response.usage_info.pages_processed


def process(pdf_bytes: bytes, document: Document) -> None:
    with stage_attempt(document.id, document.name, "ocr", f"{document.id}/document.md"):
        _, pages = extract_markdown(pdf_bytes, str(document.id), document.name)
        document.pages = pages
        write_document(document)


def request_ocr(pdf_bytes: bytes, document_id: str, document_name: str, checkpoint_key: str) -> OCRResponse:
    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    with Mistral(api_key=os.environ["MISTRAL_API_KEY"], timeout_ms=OCR_TIMEOUT_MS) as client, track_usage(
        "mistral", OCR_MODEL, "ocr", document_id, document_name,
    ) as usage:
        response = client.ocr.process(
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{encoded}",
            },
            model=OCR_MODEL,
            include_image_base64=True,
            retries=None,
        )
        usage.usage = [UsageEntry(
            model=OCR_MODEL, provider="mistral",
            cost=Decimal(response.usage_info.pages_processed) * OCR_COST_PER_PAGE,
            details={**response.usage_info.model_dump(mode="json"),
                     "cost_per_page_usd": str(OCR_COST_PER_PAGE), "cost_estimated": True},
        )]
        with get_redis() as redis:
            redis.set(checkpoint_key, json.dumps({"response": response.model_dump(mode="json"), "usage": usage.model_dump(mode="json")}))
    return response


def extract_local_markdown(pdf_bytes: bytes, directory: Path) -> tuple[str, int]:
    """Extract page Markdown with Mistral OCR and save its images locally."""
    if not os.environ["MISTRAL_API_KEY"].strip():
        raise ValueError("MISTRAL_API_KEY is empty")

    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    with Mistral(api_key=os.environ["MISTRAL_API_KEY"], timeout_ms=OCR_TIMEOUT_MS) as client:
        response = client.ocr.process(
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{encoded}",
            },
            model=OCR_MODEL,
            include_image_base64=True,
        )

    (directory / "ocr.json").write_text(response.model_dump_json(), encoding="utf-8")

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
    markdown = "\n\n".join(pages)
    logger.info("[OCR] Extracted %s pages using %s", len(pages), OCR_MODEL)
    return markdown, len(pages)
