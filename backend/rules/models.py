from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from erp import ErpEntry
from orders.models import Order
from pipeline.extraction_3.extraction import InvoiceExtraction
from suppliers.models import Supplier


class ResolvedReferences(BaseModel):
    supplier: Supplier | None
    order: Order | None
    order_ambiguous: bool = False
    entries: list[ErpEntry]


class RuleContext(ResolvedReferences):
    invoice: InvoiceExtraction
    evaluation_date: date
    claimed_by_document_id: UUID | None = None
    document_id: UUID


class RuleResult(BaseModel):
    rule: str
    passed: bool
    reason: str


class Decision(BaseModel):
    classification: Literal['PAGAR', 'NO_PAGAR', 'ESCALAR']
    reasons: list[str]
    checks: dict[str, bool]
    due_date: date | None = None
    supplier_name: str | None = None
    amount: Decimal | None = None
    claimed_by_document_id: UUID | None = None
