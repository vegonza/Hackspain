from decimal import Decimal

from pydantic import BaseModel


class InvoiceLine(BaseModel):
    description: str
    amount: Decimal


class InvoiceFeatures(BaseModel):
    invoice_number: str
    supplier_name: str
    supplier_nif: str
    iban: str
    invoice_date: str
    purchase_order: str
    line_items: list[InvoiceLine]
    tax_base: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total: Decimal
