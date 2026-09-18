from datetime import date
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
    invoice_date: date
    purchase_order: str
    line_items: list[InvoiceLine]
    tax_base: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total: Decimal


def extract_invoice_features(markdown: str) -> InvoiceFeatures:
    """Return the stable extraction contract while its implementation is pending."""
    return InvoiceFeatures(
        invoice_number="FA-2026-0001",
        supplier_name="Suministros Levante S.L.",
        supplier_nif="B46102331",
        iban="ES21 0049 1500 0512 3456 7890",
        invoice_date=date(2026, 1, 12),
        purchase_order="PO-2026-0042",
        line_items=[
            InvoiceLine(description="Cuota de servicio", amount=Decimal("5918.33")),
        ],
        tax_base=Decimal("5918.33"),
        vat_rate=Decimal("21"),
        vat_amount=Decimal("1242.85"),
        total=Decimal("7161.18"),
    )
