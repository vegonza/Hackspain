from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from postgrest.exceptions import APIError

from invoices.queue import enqueue, RETRIES, SCHEDULED, QUEUE, PROCESSING
from shared.redis import get_redis
from invoices.repository import InvoiceDetails, read_invoice_detail, Invoice, archive_invoice, read_invoice, write_invoice, create_invoice, find_invoice_by_hash
from invoices.repository import list_invoices as read_invoices
from invoices.repository import reset_invoice
from erp import ErpEntry
from extractor.extraction import InvoiceExtraction
from shared.logger import get_logger
from shared.storage import download_file, invalidate_invoice_urls, signed_url, upload_file, delete_file

logger = get_logger()
router = APIRouter(prefix="/api/invoices")


class InvoiceDetail(Invoice):
    native_text: str | None
    extraction: InvoiceExtraction | None
    erp_snapshot_id: UUID | None
    erp: ErpEntry | None


def invoice_detail(invoice_record: InvoiceDetails) -> InvoiceDetail:
    extraction = None
    native_text = None
    if invoice_record.result_path is not None:
        extraction = InvoiceExtraction.model_validate_json(download_file(invoice_record.result_path))
        native_text = download_file(f"{invoice_record.id}/native.txt").decode("utf-8")
    return InvoiceDetail(**invoice_record.model_dump(exclude={"result_path"}), native_text=native_text, extraction=extraction)


@router.get("")
def list_invoices() -> list[Invoice]:
    return read_invoices()


@router.post("", status_code=202)
def upload_invoice(file: UploadFile) -> Invoice:
    name = file.filename
    pdf_bytes = file.file.read()
    if not name or not name.lower().endswith(".pdf") or not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="invalid_pdf")

    digest = sha256(pdf_bytes).hexdigest()
    if find_invoice_by_hash(digest):
        logger.info("[INVOICES] Rejected duplicate PDF %s", name)
        raise HTTPException(status_code=409, detail="duplicate_pdf")
    invoice_record = Invoice(id=uuid4(), name=name, sha256=digest, created_at=datetime.now(timezone.utc))
    upload_file(f"{invoice_record.id}/original.pdf", pdf_bytes, "application/pdf")
    try:
        create_invoice(invoice_record)
    except APIError as error:
        if error.code != "23505":
            raise
        delete_file(f"{invoice_record.id}/original.pdf")
        logger.info("[INVOICES] Rejected concurrent duplicate PDF %s", name)
        raise HTTPException(status_code=409, detail="duplicate_pdf") from None
    logger.info("[INVOICES] Saved PDF %s (%s)", name, invoice_record.id)

    try:
        enqueue(str(invoice_record.id), name)
    except Exception:
        invoice_record.status = "error"
        write_invoice(invoice_record)
        logger.exception("[QUEUE] Could not enqueue %s", name)
        raise HTTPException(status_code=503, detail="queue_unavailable") from None
    return invoice_record


@router.get("/{invoice_id}")
def get_invoice(invoice_id: UUID) -> InvoiceDetail:
    return invoice_detail(read_invoice_detail(invoice_id))


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: UUID) -> dict[str, bool]:
    invoice_record = read_invoice(invoice_id)
    if invoice_record.status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="invoice_processing")
    invalidate_invoice_urls(str(invoice_id))
    archive_invoice(invoice_id)
    with get_redis() as redis:
        redis.hdel(RETRIES, str(invoice_id))
    logger.info("[INVOICES] Archived %s (%s)", invoice_record.name, invoice_id)
    return {"deleted": True}


@router.post("/{invoice_id}/retry", status_code=202)
def retry_invoice(invoice_id: UUID) -> Invoice:
    with get_redis() as redis, redis.lock(f"invoices:retry-lock:{invoice_id}", timeout=30):
        invoice_record = read_invoice(invoice_id)
        if invoice_record.status != "error":
            raise HTTPException(status_code=409, detail="invoice_not_failed")
        invoice_record.status = "queued"
        write_invoice(invoice_record)
        with redis.pipeline(transaction=True) as transaction:
            transaction.hdel(RETRIES, str(invoice_id))
            transaction.zrem(SCHEDULED, str(invoice_id))
            transaction.lrem(QUEUE, 0, str(invoice_id))
            transaction.lpush(QUEUE, str(invoice_id))
            transaction.execute()
    logger.info("[QUEUE] Manual retry requested for %s", invoice_record.name)
    return read_invoice(invoice_id)


@router.post("/{invoice_id}/redo", status_code=202)
def redo_invoice(invoice_id: UUID) -> Invoice:
    with get_redis() as redis, redis.lock(f"invoices:retry-lock:{invoice_id}", timeout=30):
        invoice_record = read_invoice(invoice_id)
        if invoice_record.status in ("queued", "processing") or redis.lpos(PROCESSING, str(invoice_id)) is not None:
            raise HTTPException(status_code=409, detail="invoice_processing")
        try:
            with redis.pipeline(transaction=True) as transaction:
                transaction.hdel(RETRIES, str(invoice_id))
                transaction.zrem(SCHEDULED, str(invoice_id))
                transaction.lrem(QUEUE, 0, str(invoice_id))
                transaction.execute()
            reset_invoice(invoice_id, invoice_record.name)
            enqueue(str(invoice_id), invoice_record.name)
        except Exception:
            invoice_record.status = "error"
            write_invoice(invoice_record)
            logger.exception("[QUEUE] Could not restart processing for %s", invoice_record.name)
            raise HTTPException(status_code=503, detail="queue_unavailable") from None
    logger.info("[QUEUE] Full reprocessing requested for %s", invoice_record.name)
    return read_invoice(invoice_id)


@router.get("/{invoice_id}/pdf-url")
def get_pdf_url(invoice_id: UUID) -> dict[str, str]:
    read_invoice(invoice_id)
    return {"url": signed_url(f"{invoice_id}/original.pdf")}
