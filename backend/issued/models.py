from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class Party(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    tax_id: str = Field(min_length=1, max_length=50)
    address: str = Field(min_length=1, max_length=500)
    email: str = Field(max_length=200)
    logo_url: str = Field(max_length=2000)


class Client(Party):
    id: UUID


class Company(Party):
    iban: str = Field(max_length=50)
    payment_method: str = Field(max_length=200)


class Line(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    quantity: Decimal = Field(gt=0, le=100000, decimal_places=4)
    unit_price: Decimal = Field(ge=0, le=1000000, decimal_places=4)
    tax_rate: Decimal = Field(ge=0, le=100, decimal_places=2)


class InvoiceInput(BaseModel):
    client_id: UUID
    issue_date: date
    due_date: date
    notes: str = Field(max_length=5000)
    items: list[Line] = Field(min_length=1, max_length=200)

    @model_validator(mode='after')
    def check_dates(self) -> 'InvoiceInput':
        if self.due_date < self.issue_date:
            raise ValueError('due_date precedes issue_date')
        return self


class TestTaxParty(BaseModel):
    name: str
    tax_id: str


class TestTaxParties(BaseModel):
    issuer: TestTaxParty
    client: TestTaxParty


class VerifactuTestReceipt(BaseModel):
    parties: TestTaxParties | None = None
    qr_code: str
    csv: str | None
    submitted_at: datetime | None
    pdf_path: str | None


class IssuedInvoiceSummary(BaseModel):
    id: UUID
    status: Literal['issuing', 'issued', 'paid']
    invoice_number: str
    issue_date: date
    client: Party
    items: list[Line]
    base_amount: Decimal
    total_amount: Decimal
    pdf_path: str | None


class IssuedInvoice(InvoiceInput, IssuedInvoiceSummary):
    company: Company
    tax_amount: Decimal
    created_at: datetime
    paid_at: datetime | None
    verifactu_test: VerifactuTestReceipt | None


def line_amount(line: Line) -> Decimal:
    return (line.quantity * line.unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def totals(items: list[Line]) -> tuple[Decimal, Decimal, Decimal]:
    base = sum((line_amount(item) for item in items), Decimal(0))
    tax = sum(((line_amount(item) * item.tax_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for item in items), Decimal(0))
    return base, tax, base + tax
