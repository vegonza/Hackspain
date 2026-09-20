from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from rules.models import Decision
from shared.identifiers import normalize_tax_id


def parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def euro_amount(decision: Decision, total_eur: object) -> Decimal | None:
    """Decisions published before the euro amount was stored fall back to the generated column."""
    if decision.amount_eur is not None:
        return decision.amount_eur
    if total_eur is None:
        return None
    try:
        amount = Decimal(str(total_eur))
    except InvalidOperation:
        return None
    return amount if amount.is_finite() else None


def payment_due_date(decision: Decision, invoice_date: object, supplier_nif: object,
                     terms: dict[str, int]) -> date | None:
    """Rebuild the due date from the supplier payment terms when the decision does not carry it."""
    if decision.due_date is not None:
        return decision.due_date
    issued = parse_date(invoice_date)
    payment_days = terms.get(normalize_tax_id(supplier_nif)) if isinstance(supplier_nif, str) else None
    if issued is None or payment_days is None:
        return None
    return issued + timedelta(days=payment_days)
