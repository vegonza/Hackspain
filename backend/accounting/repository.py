import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from accounting.models import (
    AccountingReport, AccountingSummary, CategorySummary, ExpenseCategory, FiscalInvoice, ReviewReason,
)
from rules.models import Decision
from shared.logger import get_logger
from shared.storage import get_client

CENT = Decimal("0.01")
SENSITIVE_CATEGORIES: set[ExpenseCategory] = {"travel", "meals", "vehicle"}
CATEGORY_RULES: tuple[tuple[ExpenseCategory, str, tuple[str, ...]], ...] = (
    ("rent", "621", ("alquiler", "arrendamiento")),
    ("repairs", "622", ("reparacion", "mantenimiento")),
    ("professional_services", "623", ("asesoria", "consultoria", "abogado", "auditoria", "gestoria")),
    ("insurance", "625", ("seguro", "poliza")),
    ("banking", "626", ("comision bancaria", "servicio bancario")),
    ("advertising", "627", ("publicidad", "marketing", "campana")),
    ("utilities", "628", ("electricidad", "agua", "internet", "telefono", "gas natural")),
    ("vehicle", "629", ("combustible", "gasolina", "diesel", "vehiculo", "aparcamiento", "taller")),
    ("travel", "629", ("hotel", "alojamiento", "tren", "avion", "taxi", "viaje")),
    ("meals", "629", ("restaurante", "comida", "catering", "dieta")),
    ("supplies", "602", ("material", "papeleria", "oficina", "suministro", "embalaje")),
)
logger = get_logger()


def normalized(value: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(character)
    )


def decimal_value(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def amount_or_zero(value: Decimal | None) -> Decimal:
    return Decimal(0) if value is None else value


def expense_category(row: dict[str, Any]) -> tuple[ExpenseCategory, str]:
    line_items = row["line_items"]
    descriptions = "" if line_items is None else " ".join(str(item["description"]) for item in line_items)
    supplier_name = "" if row["supplier_name"] is None else row["supplier_name"]
    haystack = normalized(f"{supplier_name} {descriptions}")
    for category, account_code, keywords in CATEGORY_RULES:
        if any(keyword in haystack for keyword in keywords):
            return category, account_code
    return "other", "629"


def parsed_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def quarter_of(value: date) -> int:
    return (value.month - 1) // 3 + 1


def fiscal_invoice(row: dict[str, Any]) -> FiscalInvoice:
    category, account_code = expense_category(row)
    invoice_date = parsed_date(row["invoice_date"])
    tax_base = decimal_value(row["tax_base"])
    vat_rate = decimal_value(row["vat_rate"])
    vat_amount = decimal_value(row["vat_amount"])
    total = decimal_value(row["total"])
    reasons: list[ReviewReason] = []
    decision_payload = row["payment_decision"]
    if decision_payload is None:
        reasons.append("missing_payment_decision")
    elif Decision.model_validate(decision_payload).classification == "ESCALAR":
        reasons.append("payment_review")
    if not row["invoice_number"] or not row["supplier_name"] or not row["supplier_nif"]:
        reasons.append("missing_identity")
    if invoice_date is None:
        reasons.append("invalid_date")
    if any(value is None for value in (tax_base, vat_rate, vat_amount, total)):
        reasons.append("missing_amounts")
    elif abs(total - tax_base - vat_amount) > CENT or abs(vat_amount - tax_base * vat_rate / 100) > CENT:
        reasons.append("invalid_tax_amounts")
    if category in SENSITIVE_CATEGORIES:
        reasons.append("sensitive_category")
    elif category == "other":
        reasons.append("unknown_category")
    prepared = not reasons
    return FiscalInvoice(
        document_id=row["id"], document_name=row["name"], invoice_number=row["invoice_number"],
        invoice_date=invoice_date, supplier_name=row["supplier_name"], supplier_nif=row["supplier_nif"],
        category=category, account_code=account_code, tax_base=tax_base, vat_rate=vat_rate,
        vat_amount=vat_amount, total=total,
        potential_deductible_expense=tax_base if prepared and tax_base is not None else Decimal(0),
        potential_deductible_vat=vat_amount if prepared and vat_amount is not None else Decimal(0),
        status="PREPARED" if prepared else "REVIEW", review_reasons=reasons,
    )


def read_accounting(year: int, quarter: int | None) -> AccountingReport:
    rows = get_client().table("documents").select(
        "id,name,invoice_number,invoice_date,supplier_name,supplier_nif,line_items,tax_base,vat_rate,vat_amount,total,payment_decision"
    ).is_("deleted_at", "null").execute().data
    invoices: list[FiscalInvoice] = []
    for row in rows:
        raw_date = row["invoice_date"]
        if not isinstance(raw_date, str) or not raw_date.startswith(f"{year:04d}-"):
            continue
        invoice = fiscal_invoice(row)
        if quarter is not None and (invoice.invoice_date is None or quarter_of(invoice.invoice_date) != quarter):
            continue
        invoices.append(invoice)

    categories: dict[ExpenseCategory, CategorySummary] = {}
    for invoice in invoices:
        if invoice.category not in categories:
            categories[invoice.category] = CategorySummary(
                category=invoice.category, invoice_count=0, tax_base=Decimal(0),
                vat_amount=Decimal(0), review_count=0,
            )
        summary = categories[invoice.category]
        summary.invoice_count += 1
        summary.tax_base += amount_or_zero(invoice.tax_base)
        summary.vat_amount += amount_or_zero(invoice.vat_amount)
        summary.review_count += int(invoice.status == "REVIEW")

    prepared = [invoice for invoice in invoices if invoice.status == "PREPARED"]
    review = [invoice for invoice in invoices if invoice.status == "REVIEW"]
    report = AccountingReport(
        year=year,
        quarter=quarter,
        summary=AccountingSummary(
            recorded_expenses=sum((amount_or_zero(invoice.tax_base) for invoice in invoices), Decimal(0)),
            potential_deductible_expenses=sum((invoice.potential_deductible_expense for invoice in prepared), Decimal(0)),
            potential_deductible_vat=sum((invoice.potential_deductible_vat for invoice in prepared), Decimal(0)),
            amount_under_review=sum((amount_or_zero(invoice.total) for invoice in review), Decimal(0)),
            prepared_invoices=len(prepared),
            review_invoices=len(review),
        ),
        by_category=sorted(categories.values(), key=lambda item: (-item.tax_base, item.category)),
        invoices=sorted(invoices, key=lambda invoice: (
            invoice.status != "REVIEW", invoice.invoice_date or date.min, invoice.document_name,
        )),
    )
    logger.info(
        "[ACCOUNTING] Prepared %s fiscal invoice records for %s%s",
        len(invoices), year, f" Q{quarter}" if quarter is not None else "",
    )
    return report
