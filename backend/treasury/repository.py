from datetime import date, timedelta
from decimal import Decimal

from rules.models import Decision
from shared.logger import get_logger
from shared.storage import get_client
from treasury.models import SupplierCommitment, TreasuryPayment, TreasuryReport, TreasurySummary

logger = get_logger()


def read_treasury(evaluation_date: date) -> TreasuryReport:
    rows = get_client().table("documents").select(
        "id,name,payment_decision"
    ).is_("deleted_at", "null").execute().data
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
        if decision.classification == "ESCALAR" and decision.amount_eur is not None:
            blocked_in_review += decision.amount_eur
        if decision.classification != "PAGAR":
            continue
        if decision.amount_eur is None or decision.due_date is None or decision.supplier_name is None:
            incomplete_approved += 1
            continue
        amount = decision.amount_eur
        due_date = decision.due_date
        supplier_name = decision.supplier_name
        payments.append(TreasuryPayment(
            document_id=row["id"],
            document_name=row["name"],
            supplier_name=supplier_name,
            amount=amount,
            due_date=due_date,
        ))
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
