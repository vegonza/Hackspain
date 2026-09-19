from datetime import date as Date, datetime
from decimal import Decimal
from uuid import UUID

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


class ErpPage(BaseModel):
    number: int = Field(ge=1)
    total_pages: int = Field(ge=1)
    total_entries: int = Field(ge=0)
    page_size: int = Field(ge=1)
    entries: list[ErpEntry]


class ErpSourceState(BaseModel):
    version: str = Field(min_length=1)
    uptime_seconds: int = Field(ge=0)
    entry_count: int = Field(ge=0)
    update_loaded: bool


class ErpSnapshot(BaseModel):
    fetched_at: datetime
    status_before: ErpSourceState
    status_after: ErpSourceState
    entries: list[ErpEntry]


class LinkedDocument(BaseModel):
    id: UUID
    name: str


class SavedErpEntry(ErpEntry):
    id: UUID
    documents: list[LinkedDocument] = Field(default_factory=list)


class SavedErpSnapshot(BaseModel):
    id: UUID
    fetched_at: datetime
    erp_version: str
    update_loaded: bool
    entry_count: int
    entries: list[SavedErpEntry]
