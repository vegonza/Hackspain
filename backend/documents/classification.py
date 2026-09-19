from datetime import date
from uuid import UUID

from documents.payment_notes import review_payment_notes
from pipeline.extraction_3.extraction import InvoiceExtraction
from rules.evaluator import evaluate_rules, payment_decision
from rules.models import Decision, RuleContext
from rules.resolver import resolve_references
from shared.logger import get_logger

logger = get_logger()


def classify_document(document_id: UUID, invoice: InvoiceExtraction, evaluation_date: date,
                      *, pending_review: set[str], duplicate_order: bool) -> Decision:
    """Classify an extracted invoice against its Supabase master data and pinned ERP snapshot."""
    references = resolve_references(document_id, invoice.purchase_order)
    context = RuleContext(invoice=invoice, **references.model_dump(), evaluation_date=evaluation_date,
                          pending_review=pending_review, duplicate_order=duplicate_order)
    results = evaluate_rules(context)
    if any(result.rule == 'not_paid' and not result.passed for result in results):
        decision = payment_decision(results, invoice.notes, reviewed_note_reasons=None)
    else:
        review = review_payment_notes(invoice.notes, {result.rule: result.passed for result in results})
        decision = payment_decision(results, invoice.notes, reviewed_note_reasons=[
            f'{concern.reason} Evidencia: {concern.evidence}' for concern in review.concerns
        ])
    logger.info('[RULES] Classified invoice %s (%s): %s', invoice.invoice_number, document_id, decision.classification)
    return decision
