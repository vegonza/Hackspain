from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

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
    pending_review: set[str] = Field(default_factory=set)
    duplicate_order: bool = False


class RuleResult(BaseModel):
    rule: str
    passed: bool
    reason: str


class Decision(BaseModel):
    classification: Literal['PAGAR', 'NO_PAGAR', 'ESCALAR']
    reasons: list[str]
    checks: dict[str, bool]
