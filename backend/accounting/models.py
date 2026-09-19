from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

ExpenseCategory = Literal[
    "supplies", "professional_services", "rent", "repairs", "insurance",
    "banking", "advertising", "utilities", "travel", "meals", "vehicle", "other",
]
FiscalStatus = Literal["PREPARED", "REVIEW"]
ReviewReason = Literal[
    "missing_payment_decision", "payment_review", "missing_identity", "invalid_date",
    "missing_amounts", "invalid_tax_amounts", "sensitive_category", "unknown_category",
]


class AccountingSummary(BaseModel):
    recorded_expenses: Decimal
    potential_deductible_expenses: Decimal
    potential_deductible_vat: Decimal
    amount_under_review: Decimal
    prepared_invoices: int
    review_invoices: int


class CategorySummary(BaseModel):
    category: ExpenseCategory
    invoice_count: int
    tax_base: Decimal
    vat_amount: Decimal
    review_count: int


class FiscalInvoice(BaseModel):
    document_id: UUID
    document_name: str
    invoice_number: str | None
    invoice_date: date | None
    supplier_name: str | None
    supplier_nif: str | None
    category: ExpenseCategory
    account_code: str
    tax_base: Decimal | None
    vat_rate: Decimal | None
    vat_amount: Decimal | None
    total: Decimal | None
    potential_deductible_expense: Decimal
    potential_deductible_vat: Decimal
    status: FiscalStatus
    review_reasons: list[ReviewReason]


class AccountingReport(BaseModel):
    year: int
    quarter: int | None
    summary: AccountingSummary
    by_category: list[CategorySummary]
    invoices: list[FiscalInvoice]
