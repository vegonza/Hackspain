from datetime import date as Date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from erp.warnings import ErpWarning
from shared.identifiers import normalize_tax_id


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


    @field_validator('tax_id')
    @classmethod
    def normalize_tax_id_field(cls, value: str) -> str:
        return normalize_tax_id(value)


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


class LinkedInvoice(BaseModel):
    id: UUID
    name: str


class SavedErpEntry(ErpEntry):
    id: UUID


class ErpEntryDetail(SavedErpEntry):
    model_config = ConfigDict(validate_by_name=True)

    invoices: list[LinkedInvoice] = Field(default_factory=list, validation_alias="documents")


class SavedErpSnapshot(BaseModel):
    id: UUID
    fetched_at: datetime
    erp_version: str
    update_loaded: bool
    entry_count: int
    entries: list[SavedErpEntry]
