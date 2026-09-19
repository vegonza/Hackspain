from datetime import date

from rules.amounts import amount_rules
from rules.identity import identity_rules
from rules.models import Decision, RuleContext, RuleResult


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
        RuleResult(rule='duplicate_order', passed=not context.duplicate_order,
                   reason='Varias facturas reclaman el mismo pedido.'),
        RuleResult(rule='extraction_certain', passed=not context.invoice.uncertainties,
                   reason='; '.join(context.invoice.uncertainties)),
    ])
    return results


def payment_decision(results: list[RuleResult], notes: list[str], reviewed_note_reasons: list[str] | None) -> Decision:
    """Paid ERP entries veto payment; unresolved checks or notes require review."""
    checks = {result.rule: result.passed for result in results}
    reasons = [result.reason for result in results if not result.passed]
    if not checks['not_paid']:
        return Decision(classification='NO_PAGAR', reasons=reasons, checks=checks)
    if reviewed_note_reasons is None:
        checks['payment_notes'] = not notes
        if notes:
            reasons.append('Las anotaciones de la factura están pendientes de revisión.')
    else:
        checks['payment_notes'] = not reviewed_note_reasons
        reasons.extend(reviewed_note_reasons)
    return Decision(classification='ESCALAR' if reasons else 'PAGAR',
                    reasons=reasons or ['Identidad, pedido, ERP, importes y fecha verificados.'], checks=checks)
