from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from decimal import Decimal
from pydantic import BaseModel, Field
from shared.storage import get_client
from shared.redis import get_redis
from shared.retries import RetryState
from invoices.queue import RETRIES
from pipeline.extraction_3.extraction import InvoiceExtraction
from shared.logger import get_logger
from invoices.stages import StageDetail, StageId
from erp import ErpEntry
from rules.models import Decision


class StageMetrics(BaseModel):
    stage: StageId
    cost_usd: Decimal | None = None
    duration_ms: int | None = None


INVOICE_VIRTUAL_FIELDS = {"payment_decision", "retry_attempts", "last_error", "next_retry_at", "stage_metrics", "current_stages", "total_cost_usd", "total_duration_ms", "finished_at"}


class Invoice(BaseModel):
    id: UUID
    name: str
    sha256: str
    created_at: datetime
    finished_at: datetime | None = None
    status: Literal["queued", "processing", "ready", "error"] = "queued"
    pages: int = 0
    payment_decision: Decision | None = None
    total_cost_usd: Decimal | None = None
    total_duration_ms: int | None = None
    stage_metrics: list[StageMetrics] = Field(default_factory=list)
    current_stages: list[StageId] = Field(default_factory=list)
    retry_attempts: int = 0
    last_error: str | None = None
    next_retry_at: datetime | None = None


def with_retry_state(invoice_record: Invoice, state: RetryState) -> Invoice:
    invoice_record.retry_attempts = state.attempts
    invoice_record.last_error = state.last_error
    invoice_record.next_retry_at = datetime.fromtimestamp(state.next_attempt, timezone.utc) if state.next_attempt is not None else None
    if invoice_record.status != "ready":
        if state.failed:
            invoice_record.status = "error"
        elif state.next_attempt is not None:
            invoice_record.status = "queued"
    return invoice_record


def read_invoice(invoice_id: UUID) -> Invoice:
    rows = get_client().table("documents").select("*").eq("id", str(invoice_id)).is_("deleted_at", "null").execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    with get_redis() as redis:
        payload = redis.hget(RETRIES, str(invoice_id))
    return with_retry_state(Invoice.model_validate(rows[0]), RetryState.model_validate_json(payload) if payload is not None else RetryState())


def list_invoices() -> list[Invoice]:
    invoices: list[Invoice] = []
    while True:
        rows = get_client().rpc("get_documents", {"p_offset": len(invoices), "p_limit": 1000}).execute().data
        if rows:
            with get_redis() as redis:
                states = redis.hmget(RETRIES, [row["id"] for row in rows])
            page = [with_retry_state(Invoice.model_validate(row), RetryState.model_validate_json(state) if state is not None else RetryState()) for row, state in zip(rows, states)]
            for invoice_record in page:
                if invoice_record.status not in ("ready", "error"):
                    invoice_record.finished_at = None
            invoices.extend(page)
        if len(rows) < 1000:
            return invoices


def find_invoice_by_hash(sha256: str) -> bool:
    return bool(get_client().table("documents").select("id").eq("sha256", sha256).is_("deleted_at", "null").limit(1).execute().data)


def create_invoice(invoice_record: Invoice) -> None:
    get_client().table("documents").insert(invoice_record.model_dump(mode="json", exclude=INVOICE_VIRTUAL_FIELDS)).execute()


def write_invoice(invoice_record: Invoice) -> None:
    fields = set(Invoice.model_fields) - INVOICE_VIRTUAL_FIELDS
    get_client().table("documents").upsert(invoice_record.model_dump(mode="json", include=fields)).execute()


def archive_invoice(invoice_id: UUID) -> None:
    get_client().table("documents").update({"deleted_at": datetime.now(timezone.utc).isoformat()}).eq("id", str(invoice_id)).execute()


def reset_invoice(invoice_id: UUID, name: str) -> None:
    client = get_client()
    client.table("document_stages").update({
        "status": "unavailable", "started_at": None, "finished_at": None,
        "duration_ms": None, "result_path": None,
    }).eq("document_id", str(invoice_id)).execute()
    fields = {field: None for field in InvoiceExtraction.model_fields if field not in {"notes", "uncertainties"}}
    client.table("documents").update({
        **fields, "status": "queued", "pages": 0, "erp_entry_id": None, "payment_decision": None,
    }).eq("id", str(invoice_id)).is_("deleted_at", "null").execute()
    get_logger().info("[INVOICES] Reset processing results for %s", name)


class InvoiceDetails(Invoice):
    stages: list[StageDetail]
    erp_snapshot_id: UUID | None = None
    erp: ErpEntry | None = None


def read_invoice_detail(invoice_id: UUID) -> InvoiceDetails:
    """Read invoice metadata, stage results and aggregated costs in one DB call."""
    payload = get_client().rpc("get_document_detail", {"p_document_id": str(invoice_id)}).execute().data
    if payload is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    invoice_record = InvoiceDetails.model_validate(payload)
    with get_redis() as redis:
        state = redis.hget(RETRIES, str(invoice_id))
    with_retry_state(invoice_record, RetryState.model_validate_json(state) if state is not None else RetryState())
    if invoice_record.status in ("ready", "error"):
        invoice_record.finished_at = max((stage.finished_at for stage in invoice_record.stages if stage.finished_at is not None), default=None)
    return invoice_record


def save_invoice_extraction(invoice_id: UUID, name: str, extraction: InvoiceExtraction) -> None:
    """Store searchable invoice fields; the stage artifact retains notes and uncertainties."""
    fields = extraction.model_dump(mode="json", exclude={"notes", "uncertainties"})
    for amount in ("tax_base", "vat_rate", "vat_amount", "total"):
        if fields[amount] == "":
            fields[amount] = None
    get_client().table('documents').update({**fields, 'payment_decision': None}).eq('id', str(invoice_id)).is_('deleted_at', 'null').execute()
    get_logger().info("[INVOICES] Saved extracted data for %s", name)
