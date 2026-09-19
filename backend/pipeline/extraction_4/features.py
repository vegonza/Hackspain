import re

from pydantic import BaseModel, ConfigDict

from pipeline.extraction_4.extractor import create_extractor, load_prompt
from shared.usage import UsageRecord


class InvoiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    amount: str


class InvoiceFeatures(BaseModel):
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


class SourcedInvoiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_line: int
    amount_token: int
    description: str


class SourcedInvoiceFeatures(InvoiceFeatures):
    line_items: list[SourcedInvoiceLine]


def normalize_decimal(value: str) -> str:
    value = value.translate(str.maketrans({" ": "", "\u00a0": "", "\u202f": ""}))
    if "," in value and "." in value:
        if value.rfind(".") > value.rfind(","):
            return value.replace(",", "")
        return value.replace(".", "").replace(",", ".")
    return value.replace(",", ".")


def extract_invoice_features(markdown: str, usage: UsageRecord | None = None) -> InvoiceFeatures:
    lines = markdown.splitlines()
    numeric_tokens = [re.findall(
        r"(?<![\w.,])[-+]?(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)(?![\w.,])",
        line,
    ) for line in lines]
    numbered = "\n".join(
        f"[{number}] {line} [numeric_tokens: "
        + "; ".join(f"{index}={token}" for index, token in enumerate(tokens, start=1)) + "]"
        for number, (line, tokens) in enumerate(zip(lines, numeric_tokens), start=1)
    )
    instruction = load_prompt("extractor.md")
    content = f"Extract the invoice fields from this combined document:\n\n{numbered}"
    with create_extractor() as extractor:
        extracted = extractor.run(instruction, content, SourcedInvoiceFeatures, usage=usage)
    items: list[InvoiceLine] = []
    previous_line = 0
    for item in extracted.line_items:
        if not 1 <= item.source_line <= len(lines) or item.source_line < previous_line:
            raise ValueError("Line item source references are invalid or out of order")
        amounts = numeric_tokens[item.source_line - 1]
        if not 1 <= item.amount_token <= len(amounts):
            raise ValueError(f"Line item amount token is absent from source line {item.source_line}")
        amount = amounts[item.amount_token - 1]
        normalized = normalize_decimal(amount)
        items.append(InvoiceLine(description=item.description, amount=normalized))
        previous_line = item.source_line
    totals = {field: normalize_decimal(getattr(extracted, field)) for field in ("tax_base", "vat_rate", "vat_amount", "total")}
    return InvoiceFeatures.model_validate({**extracted.model_dump(exclude={"line_items"}), **totals, "line_items": items})
