from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class DocumentErpEntry(BaseModel):
    """The ERP entry matched to this document by the reconciliation process."""
    entry_id: str
    registered_at: date
    supplier_id: str
    nif: str
    purchase_order: str
    expected_amount: Decimal
    status: Literal["PENDIENTE", "PAGADA"]


def preview_erp_entry() -> DocumentErpEntry:
    """Provide sample ERP data until reconciliation is connected."""
    return DocumentErpEntry(
        entry_id="AS-00412",
        registered_at=date(2026, 1, 13),
        supplier_id="P001",
        nif="B46102331",
        purchase_order="PO-2026-0042",
        expected_amount=Decimal("7161.18"),
        status="PENDIENTE",
    )
