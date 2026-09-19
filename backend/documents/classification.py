from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from documents.payment_notes import review_payment_notes
from pipeline.extraction_3.extraction import InvoiceExtraction
from rules.evaluator import evaluate_rules, payment_decision
from rules.models import Decision, RuleContext
from rules.resolver import claim_order, resolve_references
from shared.logger import get_logger
from shared.usage import UsageRecord

logger = get_logger()


def financial_fields(context: RuleContext, decision: Decision) -> Decision:
    if decision.classification == 'NO_PAGAR':
        return decision
    try:
        invoice_date = date.fromisoformat(context.invoice.invoice_date)
    except ValueError:
        invoice_date = None
    try:
        total = Decimal(context.invoice.total)
        amount = total if total.is_finite() else None
    except InvalidOperation:
        amount = None
    payment_days = context.supplier.payment_terms_days if context.supplier is not None else 30
    return decision.model_copy(update={
        'due_date': invoice_date + timedelta(days=payment_days) if invoice_date is not None else None,
        'supplier_name': context.supplier.legal_name if context.supplier is not None else None,
        'amount': amount,
    })


def classify_document(document_id: UUID, invoice: InvoiceExtraction, evaluation_date: date,
                      *, usage: UsageRecord | None = None) -> Decision:
    """Classify an extracted invoice against its Supabase master data and pinned ERP snapshot."""
    owner = claim_order(document_id, invoice.purchase_order)
    references = resolve_references(document_id, invoice.purchase_order)
    context = RuleContext(invoice=invoice, **references.model_dump(), evaluation_date=evaluation_date,
                          document_id=document_id, claimed_by_document_id=owner)
    results = evaluate_rules(context)
    if any(result.rule == 'not_paid' and not result.passed for result in results):
        decision = payment_decision(results, invoice.notes, reviewed_note_reasons=None)
    else:
        review = review_payment_notes(invoice.notes, {result.rule: result.passed for result in results}, usage=usage)
        decision = payment_decision(results, invoice.notes, reviewed_note_reasons=[
            f'{concern.reason} Evidencia: {concern.evidence}' for concern in review.concerns
        ])
    decision = financial_fields(context, decision)
    decision.claimed_by_document_id = owner
    logger.info('[RULES] Classified invoice %s (%s): %s', invoice.invoice_number, document_id, decision.classification)
    return decision
