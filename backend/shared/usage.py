from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterator
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
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
    model_config = ConfigDict(validate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str
    model: str
    operation: str
    invoice_id: str = Field(validation_alias="document_id")
    invoice_name: str = Field(validation_alias="document_name")
    usage: list[UsageEntry] = Field(default_factory=list)

    def storage_payload(self) -> dict[str, Any]:
        """Serialize the Supabase usage columns."""
        payload = self.model_dump(mode="json")
        payload["document_id"] = payload.pop("invoice_id")
        payload["document_name"] = payload.pop("invoice_name")
        return payload


def save_usage(record: UsageRecord) -> None:
    get_client().table("usage_log").upsert(record.storage_payload()).execute()


@contextmanager
def track_usage(provider: str, model: str, operation: str, invoice_id: str, invoice_name: str) -> Iterator[UsageRecord]:
    """Queue the final usage in Redis; a separate worker writes it to Supabase."""
    record = UsageRecord(provider=provider, model=model, operation=operation,
                         invoice_id=invoice_id, invoice_name=invoice_name)
    try:
        yield record
    finally:
        with get_redis() as redis:
            redis.hset(USAGE_OUTBOX, record.id, record.model_dump_json())
        logger.info("[USAGE] Queued %s / %s for %s", provider, model, invoice_name)
