from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from shared.usage import UsageRecord
from shared.storage import get_client
from shared.redis import get_redis
from shared.retries import RetryState
from usage.worker import RETRIES
from shared.logger import get_logger

router = APIRouter(prefix="/api/usage")
PAGE_SIZE = 25


class DailyUsage(BaseModel):
    date: str
    calls: int = 0
    cost_usd: Decimal = Decimal(0)
    operations: dict[str, Decimal] = Field(default_factory=dict)


class UsageSummary(BaseModel):
    calls: int
    pages: int
    cost_usd: Decimal
    average_invoice_cost_usd: Decimal = Field(validation_alias="average_document_cost_usd")


class UsageResponse(BaseModel):
    records: list[UsageRecord]
    total: int
    page_size: int = PAGE_SIZE
    summary: UsageSummary
    daily: list[DailyUsage]
    failed_pending: int = 0


@router.get("")
def get_usage(page: int = Query(default=0, ge=0)) -> UsageResponse:
    result = get_client().rpc("get_usage_dashboard", {"p_page": page}).execute()
    response = UsageResponse.model_validate(result.data)
    with get_redis() as redis:
        response.failed_pending = sum(RetryState.model_validate_json(payload).failed for payload in redis.hvals(RETRIES))
    return response


@router.post("/retry")
def retry_failed_usage() -> dict[str, int]:
    count = 0
    with get_redis() as redis:
        for identifier, payload in redis.hscan_iter(RETRIES):
            if RetryState.model_validate_json(payload).failed:
                redis.hdel(RETRIES, identifier)
                count += 1
    get_logger().info("[USAGE] Manual retry requested for %s records", count)
    return {"retried": count}
