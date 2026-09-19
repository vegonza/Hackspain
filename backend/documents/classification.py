from datetime import date
from uuid import UUID

from documents.payment_notes import review_payment_notes
from pipeline.extraction_3.extraction import InvoiceExtraction
from rules.evaluator import evaluate_rules, payment_decision
from rules.models import Decision, RuleContext
from rules.resolver import claim_order, resolve_references
from shared.logger import get_logger
from shared.usage import UsageRecord

logger = get_logger()


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
    decision.claimed_by_document_id = owner
    logger.info('[RULES] Classified invoice %s (%s): %s', invoice.invoice_number, document_id, decision.classification)
    return decision
