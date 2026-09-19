from typing import Literal
from decimal import Decimal

from pydantic import BaseModel

from documents.repository import Document
from documents.stages import StageId, StageDetail
from shared.storage import download_file
from pipeline.diff import DiffLine, markdown_diff

StageStatus = Literal["queued", "processing", "ready", "error", "retrying", "unavailable"]


class DocumentStage(BaseModel):
    id: StageId
    status: StageStatus
    depends_on: list[StageId]
    format: Literal["markdown", "text", "json"]
    duration_ms: int | None = None
    cost_usd: Decimal | None = None
    content: str | None = None
    diff: list[DiffLine] | None = None


def document_stages(document: Document, saved_stages: list[StageDetail]) -> list[DocumentStage]:
    """Expose saved phase results, metrics and the OCR-to-merge diff."""
    records = {record.stage: record for record in saved_stages}
    stages: list[DocumentStage] = []
    pending = [stage for stage in ("text", "ocr", "merge", "extraction") if records[stage].status != "ready"]
    for stage_id in ("ocr", "text", "merge", "extraction"):
        record = records[stage_id]
        status: StageStatus = record.status
        if pending and stage_id == pending[0]:
            if document.next_retry_at is not None:
                status = "retrying"
            elif document.status == "error":
                status = "error"
            elif document.status == "queued":
                status = "queued"
        content = download_file(record.result_path).decode("utf-8") if record.status == "ready" and record.result_path is not None else None
        stages.append(DocumentStage(id=stage_id, status=status,
                                    depends_on=["ocr", "text"] if stage_id == "merge" else ["merge"] if stage_id == "extraction" else [],
                                    format="text" if stage_id == "text" else "json" if stage_id == "extraction" else "markdown",
                                    content=content, duration_ms=record.duration_ms,
                                    cost_usd=Decimal(0) if stage_id == "text" and record.status == "ready" else record.cost_usd))
    markdown = stages[0].content or ""
    if stages[2].content is not None:
        stages[2].diff = markdown_diff(markdown, stages[2].content)

    return stages
