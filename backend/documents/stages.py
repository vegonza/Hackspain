from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from shared.logger import get_logger
from shared.storage import get_client

StageId = Literal["ocr", "text", "merge"]
logger = get_logger()


class StageRecord(BaseModel):
    document_id: UUID
    stage: StageId
    status: Literal["unavailable", "queued", "processing", "ready", "error"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    result_path: str | None = None


class StageDetail(StageRecord):
    cost_usd: Decimal | None = None


def start_stage(document_id: UUID, name: str, stage: StageId) -> None:
    get_client().table("document_stages").update({
        "status": "processing", "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None, "duration_ms": None, "result_path": None,
    }).eq("document_id", str(document_id)).eq("stage", stage).execute()
    logger.info("[PIPELINE] Started %s for %s", stage, name)


def finish_stage(document_id: UUID, name: str, stage: StageId, duration_ms: int,
                 result_path: str) -> None:
    """Publish an already stored artifact and the successful attempt's metrics."""
    get_client().table("document_stages").update({
        "status": "ready", "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms, "result_path": result_path,
    }).eq("document_id", str(document_id)).eq("stage", stage).execute()
    logger.info("[PIPELINE] Completed %s for %s in %s ms", stage, name, duration_ms)


def fail_stage(document_id: UUID, name: str, stage: StageId, duration_ms: int) -> None:
    get_client().table("document_stages").update({
        "status": "error", "finished_at": datetime.now(timezone.utc).isoformat(), "duration_ms": duration_ms,
    }).eq("document_id", str(document_id)).eq("stage", stage).execute()
    logger.info("[PIPELINE] Failed %s for %s after %s ms", stage, name, duration_ms)


def read_stage_costs(document_id: UUID) -> dict[str, Decimal]:
    rows = get_client().rpc("get_document_stage_costs", {"p_document_id": str(document_id)}).execute().data
    return {row["stage"]: Decimal(row["cost_usd"]) for row in rows}
