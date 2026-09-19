from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from shared.usage import UsageRecord, read_usage

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
    records = read_usage()
    daily: dict[str, DailyUsage] = {}
    for record in records:
        day = record.created_at.date().isoformat()
        if day not in daily:
            daily[day] = DailyUsage(date=day)
        daily[day].calls += 1
        cost = sum((entry.cost for entry in record.usage), Decimal(0))
        daily[day].cost_usd += cost
        operations = daily[day].operations
        operations[record.operation] = operations.get(record.operation, Decimal(0)) + cost
    total_cost = sum((entry.cost for record in records for entry in record.usage), Decimal(0))
    days = max(1, (datetime.now(timezone.utc).date() - records[-1].created_at.astimezone(timezone.utc).date()).days + 1) if records else 1
    return UsageResponse(
        records=records[page * PAGE_SIZE:(page + 1) * PAGE_SIZE], total=len(records),
        summary=UsageSummary(
            calls=len(records),
            pages=sum(int(entry.details.get("pages_processed", 0)) for record in records for entry in record.usage),
            cost_usd=total_cost,
            average_daily_cost_usd=total_cost / days,
        ),
        daily=sorted(daily.values(), key=lambda item: item.date)[-14:],
    )
