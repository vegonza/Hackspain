from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from postgrest.exceptions import APIError

from documents.queue import enqueue, RETRIES, SCHEDULED, QUEUE
from shared.redis import get_redis
from documents.repository import DocumentSnapshot, read_document_detail, Document, archive_document, read_document, write_document, create_document, find_document_by_hash
from documents.repository import list_documents as read_documents
from documents.pipeline import DocumentStage, document_stages
from documents.stages import read_stage_costs
from decimal import Decimal
from documents.features import InvoiceFeatures, extract_invoice_features
from shared.logger import get_logger
from shared.storage import invalidate_document_urls, signed_url, upload_file, delete_file

logger = get_logger()
router = APIRouter(prefix="/api/documents")


class DocumentDetail(Document):
    stages: list[DocumentStage]
    features: InvoiceFeatures | None


def document_detail(document: DocumentSnapshot) -> DocumentDetail:
    stages = document_stages(document, document.stages)
    markdown = stages[0].content
    features = extract_invoice_features(markdown) if markdown is not None else None
    return DocumentDetail(**document.model_dump(exclude={"stages"}), stages=stages, features=features)


@router.get("")
def list_documents() -> list[Document]:
    return read_documents()


@router.post("", status_code=202)
def upload_document(file: UploadFile) -> Document:
    name = file.filename
    pdf_bytes = file.file.read()
    if not name or not name.lower().endswith(".pdf") or not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="invalid_pdf")

    digest = sha256(pdf_bytes).hexdigest()
    if find_document_by_hash(digest):
        logger.info("[DOCUMENTS] Rejected duplicate PDF %s", name)
        raise HTTPException(status_code=409, detail="duplicate_pdf")
    document = Document(id=uuid4(), name=name, sha256=digest, created_at=datetime.now(timezone.utc))
    upload_file(f"{document.id}/original.pdf", pdf_bytes, "application/pdf")
    try:
        create_document(document)
    except APIError as error:
        if error.code != "23505":
            raise
        delete_file(f"{document.id}/original.pdf")
        logger.info("[DOCUMENTS] Rejected concurrent duplicate PDF %s", name)
        raise HTTPException(status_code=409, detail="duplicate_pdf") from None
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
    return document_detail(read_document_detail(document_id))


@router.delete("/{document_id}")
def delete_document(document_id: UUID) -> dict[str, bool]:
    document = read_document(document_id)
    if document.status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="document_processing")
    invalidate_document_urls(str(document_id))
    archive_document(document_id)
    with get_redis() as redis:
        redis.delete(f"documents:ocr:{document_id}")
        redis.hdel(RETRIES, str(document_id))
    logger.info("[DOCUMENTS] Archived %s (%s)", document.name, document_id)
    return {"deleted": True}


@router.post("/{document_id}/retry", status_code=202)
def retry_document(document_id: UUID) -> Document:
    with get_redis() as redis, redis.lock(f"documents:retry-lock:{document_id}", timeout=30):
        document = read_document(document_id)
        if document.status != "error":
            raise HTTPException(status_code=409, detail="document_not_failed")
        document.status = "queued"
        write_document(document)
        with redis.pipeline(transaction=True) as transaction:
            transaction.hdel(RETRIES, str(document_id))
            transaction.zrem(SCHEDULED, str(document_id))
            transaction.lrem(QUEUE, 0, str(document_id))
            transaction.lpush(QUEUE, str(document_id))
            transaction.execute()
    logger.info("[QUEUE] Manual retry requested for %s", document.name)
    return read_document(document_id)


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


@router.get("/{document_id}/stage-costs")
def get_stage_costs(document_id: UUID) -> dict[str, Decimal]:
    read_document(document_id)
    return read_stage_costs(document_id)
