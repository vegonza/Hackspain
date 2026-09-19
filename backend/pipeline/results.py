from typing import Literal
from decimal import Decimal

from pydantic import BaseModel

from invoices.repository import Invoice
from invoices.stages import StageId, StageDetail
from shared.storage import download_file

StageStatus = Literal["queued", "processing", "ready", "error", "retrying", "unavailable"]


class InvoiceStage(BaseModel):
    id: StageId
    status: StageStatus
    depends_on: list[StageId]
    format: Literal["markdown", "text", "json"]
    duration_ms: int | None = None
    cost_usd: Decimal | None = None
    content: str | None = None


def invoice_stages(invoice_record: Invoice, saved_stages: list[StageDetail]) -> list[InvoiceStage]:
    """Expose saved phase results, metrics."""
    records = {record.stage: record for record in saved_stages}
    stages: list[InvoiceStage] = []
    pending = [stage for stage in ("text", "ocr", "extraction") if records[stage].status != "ready"]
    for stage_id in ("ocr", "text", "extraction"):
        record = records[stage_id]
        status: StageStatus = record.status
        if pending and stage_id == pending[0]:
            if invoice_record.next_retry_at is not None:
                status = "retrying"
            elif invoice_record.status == "error":
                status = "error"
            elif invoice_record.status == "queued":
                status = "queued"
        content = download_file(record.result_path).decode("utf-8") if record.status == "ready" and record.result_path is not None else None
        if stage_id == "ocr" and content is not None:
            # Stored Markdown uses a fixed image prefix; expose the current API route.
            content = content.replace("/api/documents/", "/api/invoices/")
        stages.append(InvoiceStage(id=stage_id, status=status,
                                    depends_on=["ocr", "text"] if stage_id == "extraction" else [],
                                    format="text" if stage_id == "text" else "json" if stage_id == "extraction" else "markdown",
                                    content=content, duration_ms=record.duration_ms,
                                    cost_usd=Decimal(0) if stage_id == "text" and record.status == "ready" else record.cost_usd))
    return stages
