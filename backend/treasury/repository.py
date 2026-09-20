from datetime import date, timedelta
from decimal import Decimal

from rules.forecast import euro_amount, payment_due_date
from rules.models import Decision
from shared.logger import get_logger
from shared.storage import get_client
from suppliers.repository import payment_terms
from treasury.models import SupplierCommitment, TreasuryPayment, TreasuryReport, TreasurySummary

logger = get_logger()


def read_treasury(evaluation_date: date) -> TreasuryReport:
    rows = get_client().table("documents").select(
        "id,name,invoice_date,supplier_nif,supplier_name,total_eur,payment_decision"
    ).is_("deleted_at", "null").execute().data
    terms = payment_terms()
    overdue = Decimal(0)
    next_7_days = Decimal(0)
    next_30_days = Decimal(0)
    blocked_in_review = Decimal(0)
    suppliers: dict[str, SupplierCommitment] = {}
    payments: list[TreasuryPayment] = []
    incomplete_approved = 0
    seven_day_limit = evaluation_date + timedelta(days=7)
    thirty_day_limit = evaluation_date + timedelta(days=30)

    for row in rows:
        if row["payment_decision"] is None:
            continue
        decision = Decision.model_validate(row["payment_decision"])
        amount = euro_amount(decision, row.get("total_eur"))
        if decision.classification == "ESCALAR" and amount is not None:
            blocked_in_review += amount
        if decision.classification != "PAGAR":
            continue
        due_date = payment_due_date(decision, row.get("invoice_date"), row.get("supplier_nif"), terms)
        supplier_name = decision.supplier_name or row.get("supplier_name")
        if amount is None or due_date is None or not supplier_name:
            incomplete_approved += 1
            continue
        payments.append(TreasuryPayment(
            document_id=row["id"],
            document_name=row["name"],
            supplier_name=supplier_name,
            amount=amount,
            due_date=due_date,
        ))
        if due_date < evaluation_date:
            overdue += amount
        if evaluation_date <= due_date <= seven_day_limit:
            next_7_days += amount
        if evaluation_date <= due_date <= thirty_day_limit:
            next_30_days += amount
        if supplier_name not in suppliers:
            suppliers[supplier_name] = SupplierCommitment(
                supplier_name=supplier_name,
                approved_invoices=1,
                committed_amount=amount,
                next_due_date=due_date,
            )
        else:
            commitment = suppliers[supplier_name]
            commitment.approved_invoices += 1
            commitment.committed_amount += amount
            commitment.next_due_date = min(commitment.next_due_date, due_date)

    if incomplete_approved:
        logger.warning(
            "[TREASURY] Excluded %s approved decisions without complete financial fields; reprocess them to forecast payment",
            incomplete_approved,
        )

    return TreasuryReport(
        summary=TreasurySummary(
            overdue=overdue,
            next_7_days=next_7_days,
            next_30_days=next_30_days,
            blocked_in_review=blocked_in_review,
        ),
        by_supplier=sorted(suppliers.values(), key=lambda supplier: (
            supplier.next_due_date, supplier.supplier_name,
        )),
        payments=sorted(payments, key=lambda payment: (
            payment.due_date, payment.supplier_name, payment.document_name,
        )),
    )
