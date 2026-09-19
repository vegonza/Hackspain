from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from shared.usage import UsageRecord
from shared.storage import get_client

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
    average_daily_cost_usd: Decimal


class UsageResponse(BaseModel):
    records: list[UsageRecord]
    total: int
    page_size: int = PAGE_SIZE
    summary: UsageSummary
    daily: list[DailyUsage]


@router.get("")
def get_usage(page: int = Query(default=0, ge=0)) -> UsageResponse:
    result = get_client().rpc("get_usage_dashboard", {"p_page": page}).execute()
    return UsageResponse.model_validate(result.data)
