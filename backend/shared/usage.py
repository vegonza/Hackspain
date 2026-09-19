from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterator
from uuid import uuid4

from pydantic import BaseModel, Field
from shared.logger import get_logger
from shared.storage import get_client
from shared.redis import get_redis

logger = get_logger()
USAGE_OUTBOX = "usage:outbox"


class UsageEntry(BaseModel):
    model: str
    provider: str
    cost: Decimal
    details: dict[str, Any]


class UsageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str
    model: str
    operation: str
    document_id: str
    document_name: str
    usage: list[UsageEntry] = Field(default_factory=list)


def save_usage(record: UsageRecord) -> None:
    get_client().table("usage_log").upsert(record.model_dump(mode="json")).execute()


@contextmanager
def track_usage(provider: str, model: str, operation: str, document_id: str, document_name: str) -> Iterator[UsageRecord]:
    """Queue the final usage in Redis; a separate worker writes it to Supabase."""
    record = UsageRecord(provider=provider, model=model, operation=operation,
                         document_id=document_id, document_name=document_name)
    try:
        yield record
    finally:
        with get_redis() as redis:
            redis.hset(USAGE_OUTBOX, record.id, record.model_dump_json())
        logger.info("[USAGE] Queued %s / %s for %s", provider, model, document_name)
