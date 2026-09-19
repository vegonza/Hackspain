from datetime import date as Date
from decimal import Decimal

from pydantic import BaseModel, Field

from erp.warnings import ErpWarning


class ErpEntry(BaseModel):
    """Normalized ERP entry; original values survive parsing failures."""

    entry_id: str
    supplier_id: str
    tax_id: str
    order_id: str
    # Preserve unexpected statuses so reconciliation can flag them.
    status: str
    raw_date: str
    raw_amount: str
    date: Date | None = None
    amount: Decimal | None = None
    warnings: list[ErpWarning] = Field(default_factory=list)
