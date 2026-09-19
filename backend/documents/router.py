from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import RedirectResponse

from documents.queue import enqueue
from documents.repository import Document, archive_document, read_document, write_document
from documents.repository import list_documents as read_documents
from documents.features import InvoiceFeatures, extract_invoice_features
from shared.logger import get_logger
from shared.storage import download_file, invalidate_document_urls, signed_url, upload_file

logger = get_logger()
router = APIRouter(prefix="/api/documents")


class DocumentDetail(Document):
    markdown: str
    features: InvoiceFeatures | None


def document_detail(document: Document) -> DocumentDetail:
    markdown = download_file(f"{document.id}/document.md").decode("utf-8") if document.status == "ready" else ""
    features = extract_invoice_features(markdown) if document.status == "ready" else None
    return DocumentDetail(**document.model_dump(), markdown=markdown, features=features)


@router.get("")
def list_documents() -> list[Document]:
    return read_documents()


@router.post("", status_code=202)
def upload_document(file: UploadFile) -> Document:
    name = file.filename
    pdf_bytes = file.file.read()
    if not name or not name.lower().endswith(".pdf") or not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="invalid_pdf")

    document = Document(id=uuid4(), name=name, created_at=datetime.now(timezone.utc))
    upload_file(f"{document.id}/original.pdf", pdf_bytes, "application/pdf")
    write_document(document)
    logger.info("[DOCUMENTS] Saved PDF %s (%s)", name, document.id)

    try:
        enqueue(str(document.id), name)
    except Exception:
        document.status = "error"
        write_document(document)
        logger.exception("[QUEUE] Could not enqueue %s", name)
        raise HTTPException(status_code=503, detail="queue_unavailable") from None
    return document


@router.get("/{document_id}")
def get_document(document_id: UUID) -> DocumentDetail:
    return document_detail(read_document(document_id))


@router.delete("/{document_id}")
def delete_document(document_id: UUID) -> dict[str, bool]:
    document = read_document(document_id)
    if document.status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="document_processing")
    invalidate_document_urls(str(document_id))
    archive_document(document_id)
    logger.info("[DOCUMENTS] Archived %s (%s)", document.name, document_id)
    return {"deleted": True}


@router.get("/{document_id}/pdf-url")
def get_pdf_url(document_id: UUID) -> dict[str, str]:
    read_document(document_id)
    return {"url": signed_url(f"{document_id}/original.pdf")}


@router.get("/{document_id}/images/{filename}")
def get_image(document_id: UUID, filename: str) -> RedirectResponse:
    read_document(document_id)
    if not filename.startswith("page-") or not filename.endswith(".jpg") or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="image_not_found")
    return RedirectResponse(signed_url(f"{document_id}/{filename}"), headers={"Cache-Control": "no-store"})
