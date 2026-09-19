from typing import Literal
from decimal import Decimal

from pydantic import BaseModel

from documents.repository import Document
from documents.stages import StageId, StageDetail
from shared.storage import download_file
from documents.pipeline_preview import PREVIEW_DOCUMENT_ID, EXTRACTED_TEXT, MERGED_MARKDOWN, DiffLine, markdown_diff

StageStatus = Literal["queued", "processing", "ready", "error", "retrying", "unavailable"]


class DocumentStage(BaseModel):
    id: StageId
    status: StageStatus
    depends_on: list[StageId]
    format: Literal["markdown", "text"]
    duration_ms: int | None = None
    cost_usd: Decimal | None = None
    content: str | None = None
    diff: list[DiffLine] | None = None


def document_stages(document: Document, saved_stages: list[StageDetail]) -> list[DocumentStage]:
    """Expose OCR progress and the integration points for extraction and merging.

    OCR and text extraction are independent; merging consumes both outputs.
    Unconnected processors stay unavailable instead of implying queued work.
    """
    records = {record.stage: record for record in saved_stages}
    stages: list[DocumentStage] = []
    for stage_id in ("ocr", "text", "merge"):
        record = records[stage_id]
        status: StageStatus = record.status
        if stage_id == "ocr" and record.status != "ready":
            if document.next_retry_at is not None:
                status = "retrying"
            elif document.status == "error":
                status = "error"
            elif document.status == "queued":
                status = "queued"
        content = download_file(record.result_path).decode("utf-8") if record.status == "ready" and record.result_path is not None else None
        stages.append(DocumentStage(id=stage_id, status=status,
                                    depends_on=["ocr", "text"] if stage_id == "merge" else [],
                                    format="text" if stage_id == "text" else "markdown",
                                    content=content, duration_ms=record.duration_ms, cost_usd=record.cost_usd))
    markdown = stages[0].content or ""
    if stages[2].content is not None:
        stages[2].diff = markdown_diff(markdown, stages[2].content)

    if str(document.id) == PREVIEW_DOCUMENT_ID and document.status == "ready":
        stages[1].status = "ready"
        stages[1].content = EXTRACTED_TEXT
        stages[1].cost_usd = Decimal("0")
        stages[2].status = "ready"
        stages[2].content = MERGED_MARKDOWN
        stages[2].cost_usd = Decimal("0.0007")
        stages[2].diff = markdown_diff(markdown, MERGED_MARKDOWN)
        for stage, duration in zip(stages, (8420, 180, 1260)):
            stage.duration_ms = duration
    return stages
