import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from pipeline.extraction_3.extractor import create_extractor, load_prompt
from shared.usage import UsageRecord


class InvoiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    amount: str


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_number: str
    supplier_name: str
    supplier_nif: str
    iban: str
    invoice_date: str
    purchase_order: str
    line_items: list[InvoiceLine]
    tax_base: str
    vat_rate: str
    vat_amount: str
    total: str
    notes: list[str]
    uncertainties: list[str]


def normalize_decimal(value: str) -> str:
    value = value.translate(str.maketrans({" ": "", "\u00a0": "", "\u202f": ""}))
    if "," in value and "." in value:
        if value.rfind(".") > value.rfind(","):
            return value.replace(",", "")
        return value.replace(".", "").replace(",", ".")
    return value.replace(",", ".")


def extract_invoice(
    native_text: str, markdown: str, page_images: Sequence[bytes], usage: UsageRecord | None = None,
) -> InvoiceExtraction:
    instruction = load_prompt("extractor.md")
    sources = json.dumps({"native_text": native_text, "ocr_markdown": markdown}, ensure_ascii=False)
    content = f"Extract the invoice fields from these text sources and the attached page images: {sources}"
    with create_extractor() as extractor:
        extracted = extractor.run(instruction, content, InvoiceExtraction, usage=usage, page_images=page_images)
    items = [InvoiceLine(description=item.description, amount=normalize_decimal(item.amount)) for item in extracted.line_items]
    totals = {field: normalize_decimal(getattr(extracted, field)) for field in ("tax_base", "vat_rate", "vat_amount", "total")}
    return InvoiceExtraction.model_validate({**extracted.model_dump(exclude={"line_items"}), **totals, "line_items": items})
