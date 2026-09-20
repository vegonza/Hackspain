from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from extractor.categories import InvoiceCategory


class CategorySpending(BaseModel):
    category: InvoiceCategory
    amount_eur: Decimal


class SpendingDistribution(BaseModel):
    total_eur: Decimal
    categories: list[CategorySpending]


class VatDeduction(BaseModel):
    total_eur: Decimal
    deductible_eur: Decimal
    foreign_eur: Decimal


class OperationAverageCost(BaseModel):
    operation: Literal["extraction", "classification", "categorization"]
    average_document_cost_usd: Decimal


class UsageDistribution(BaseModel):
    average_document_cost_usd: Decimal
    operations: list[OperationAverageCost]


class ProcessingMetrics(BaseModel):
    average_duration_ms: Decimal | None
    seconds_per_invoice: Decimal | None
    workers: int


class AnalyticsOverview(BaseModel):
    spending: SpendingDistribution
    vat: VatDeduction
    usage: UsageDistribution
    processing: ProcessingMetrics
