from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TreasurySummary(BaseModel):
    overdue: Decimal
    next_7_days: Decimal
    next_30_days: Decimal
    blocked_in_review: Decimal


class SupplierCommitment(BaseModel):
    supplier_name: str
    approved_invoices: int
    committed_amount: Decimal
    next_due_date: date


class TreasuryPayment(BaseModel):
    document_id: UUID
    document_name: str
    supplier_name: str
    amount: Decimal
    due_date: date


class TreasuryReport(BaseModel):
    summary: TreasurySummary
    by_supplier: list[SupplierCommitment]
    payments: list[TreasuryPayment]
