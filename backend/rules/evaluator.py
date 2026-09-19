from datetime import date

from rules.amounts import amount_rules
from rules.identity import identity_rules
from rules.models import Decision, RuleContext, RuleFailure, RuleResult


def evaluate_rules(context: RuleContext) -> list[RuleResult]:
    """Evaluate Norma_Pagos_v3 and reconciliation checks without I/O or AI calls."""
    results = identity_rules(context) + amount_rules(context)
    try:
        valid_date = date.fromisoformat(context.invoice.invoice_date) <= context.evaluation_date
    except ValueError:
        valid_date = False
    results.extend([
        RuleResult(rule='date', passed=valid_date, reason='La fecha de factura es inválida, ilegible o futura.'),
        RuleResult(rule='pending_review', passed=context.order is not None and not context.order.review_required,
                   reason='El pedido tiene una revisión pendiente o no se puede verificar.'),
        RuleResult(rule='order_claim', passed=context.claimed_by_invoice_id == context.invoice_id,
                   reason='No se puede reservar el pedido de forma exclusiva para esta factura.'),
        RuleResult(rule='extraction_certain', passed=not context.invoice.uncertainties,
                   reason='; '.join(context.invoice.uncertainties)),
    ])
    return results


NOTES_PENDING_REASON = 'Las anotaciones de la factura están pendientes de revisión.'
VERIFIED_REASON = 'Identidad, pedido, ERP, importes y fecha verificados.'


def payment_decision(results: list[RuleResult], notes: list[str], reviewed_note_reasons: list[str] | None) -> Decision:
    """Paid ERP entries veto payment; unresolved checks or notes require review."""
    checks = {result.rule: result.passed for result in results}
    failures = [RuleFailure(rule=result.rule, reason=result.reason) for result in results if not result.passed]
    if not checks['not_paid']:
        return Decision(classification='NO_PAGAR', reasons=[failure.reason for failure in failures],
                        checks=checks, failures=failures)
    if reviewed_note_reasons is None:
        checks['payment_notes'] = not notes
        if notes:
            failures.append(RuleFailure(rule='payment_notes', reason=NOTES_PENDING_REASON))
    else:
        checks['payment_notes'] = not reviewed_note_reasons
        failures.extend(RuleFailure(rule='payment_notes', reason=reason) for reason in reviewed_note_reasons)
    reasons = [failure.reason for failure in failures]
    return Decision(classification='ESCALAR' if failures else 'PAGAR',
                    reasons=reasons or [VERIFIED_REASON], checks=checks, failures=failures)
