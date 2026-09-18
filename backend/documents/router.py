from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import RedirectResponse

from documents.queue import enqueue
from documents.repository import DATA_DIR, Document, document_directory, read_document, write_document
from documents.features import InvoiceFeatures, extract_invoice_features
from shared.logger import get_logger
from shared.storage import download_file, invalidate_document_urls, signed_url, upload_file

logger = get_logger()
router = APIRouter(prefix="/api/documents")


class DocumentDetail(Document):
    markdown: str
    features: InvoiceFeatures | None


def document_detail(directory: Path) -> DocumentDetail:
    document = read_document(directory)
    markdown = download_file(f"{document.id}/document.md").decode("utf-8") if document.status == "ready" else ""
    features = extract_invoice_features(markdown) if document.status == "ready" else None
    return DocumentDetail(**document.model_dump(), markdown=markdown, features=features)


@router.get("")
def list_documents() -> list[Document]:
    documents = [read_document(path.parent) for path in DATA_DIR.glob("*/metadata.json")]
    return sorted(documents, key=lambda document: document.created_at, reverse=True)


@router.post("", status_code=202)
def upload_document(file: UploadFile) -> Document:
    name = file.filename
    pdf_bytes = file.file.read()
    if not name or not name.lower().endswith(".pdf") or not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="invalid_pdf")

    document = Document(id=uuid4(), name=name, created_at=datetime.now(timezone.utc))
    directory = DATA_DIR / str(document.id)
    directory.mkdir(parents=True)
    upload_file(f"{document.id}/original.pdf", pdf_bytes, "application/pdf")
    write_document(directory, document)
    logger.info("[DOCUMENTS] Saved PDF %s (%s)", name, document.id)

    try:
        enqueue(str(document.id), name)
    except Exception:
        document.status = "error"
        write_document(directory, document)
        logger.exception("[QUEUE] Could not enqueue %s", name)
        raise HTTPException(status_code=503, detail="queue_unavailable") from None
    return document


@router.get("/{document_id}")
def get_document(document_id: UUID) -> DocumentDetail:
    return document_detail(document_directory(document_id))


@router.delete("/{document_id}")
def delete_document(document_id: UUID) -> dict[str, bool]:
    directory = document_directory(document_id)
    document = read_document(directory)
    if document.status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="document_processing")
    trash_directory = DATA_DIR / ".trash"
    invalidate_document_urls(str(document_id))
    try:
        trash_directory.mkdir(exist_ok=True)
        directory.rename(trash_directory / str(document_id))
    except OSError:
        logger.exception("[DOCUMENTS] Could not move %s to trash", document.name)
        raise HTTPException(status_code=500, detail="delete_failed") from None
    logger.info("[DOCUMENTS] Moved %s to trash (%s)", document.name, document_id)
    return {"deleted": True}


@router.get("/{document_id}/pdf-url")
def get_pdf_url(document_id: UUID) -> dict[str, str]:
    document_directory(document_id)
    return {"url": signed_url(f"{document_id}/original.pdf")}


@router.get("/{document_id}/images/{filename}")
def get_image(document_id: UUID, filename: str) -> RedirectResponse:
    document_directory(document_id)
    if not filename.startswith("page-") or not filename.endswith(".jpg") or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="image_not_found")
    return RedirectResponse(signed_url(f"{document_id}/{filename}"), headers={"Cache-Control": "no-store"})
