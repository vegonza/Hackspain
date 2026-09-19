from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rules.currency import reconciliation_rate, to_euros
from rules.models import RuleContext, RuleResult

TOLERANCE = Decimal('0.01')


def decimal(value: str) -> Decimal | None:
    try:
        result = Decimal(value)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def amount_rules(context: RuleContext) -> list[RuleResult]:
    invoice = context.invoice
    base, rate, vat, total = (decimal(value) for value in (invoice.tax_base, invoice.vat_rate, invoice.vat_amount, invoice.total))
    exchange_rate = reconciliation_rate(invoice.currency)
    total_eur = to_euros(total, exchange_rate) if total is not None and exchange_rate is not None else None
    lines = [decimal(line.amount) for line in invoice.line_items]
    results: list[RuleResult] = []

    def check(rule: str, passed: bool, reason: str) -> None:
        results.append(RuleResult(rule=rule, passed=passed, reason=reason))

    check('currency', exchange_rate is not None,
          'La moneda está ausente o no tiene un tipo de cambio fijo para conciliar en EUR.')
    check('amounts_readable', all(value is not None for value in (base, rate, vat, total, *lines)),
          'Faltan importes legibles o no son decimales válidos.')
    expected_vat: Decimal | None = None
    if base is not None and rate is not None:
        try:
            expected_vat = (base * rate / 100).quantize(TOLERANCE, rounding=ROUND_HALF_UP)
        except InvalidOperation:
            pass
    check('vat', vat is not None and expected_vat is not None and exchange_rate is not None and abs(vat - expected_vat) * exchange_rate <= TOLERANCE,
          'El IVA no corresponde a la base y al tipo impreso (tolerancia 0.01 EUR).')
    check('total', total is not None and base is not None and vat is not None and exchange_rate is not None and abs(total - base - vat) * exchange_rate <= TOLERANCE,
          'El total no coincide con base más IVA (tolerancia 0.01 EUR).')
    check('line_sum', base is not None and bool(lines) and all(value is not None for value in lines)
          and exchange_rate is not None
          and abs(sum((value for value in lines if value is not None), Decimal(0)) - base) * exchange_rate <= TOLERANCE,
          'La suma de conceptos no coincide con la base (tolerancia 0.01 EUR).')
    order = context.order
    check('order_amount', order is not None and total_eur is not None and abs(total_eur - order.amount) <= TOLERANCE,
          'No se puede verificar que el total coincida con el importe del pedido (tolerancia 0.01 EUR).')
    entries = context.entries
    check('erp_amount', len(entries) == 1 and total_eur is not None and entries[0].amount is not None
          and abs(total_eur - entries[0].amount) <= TOLERANCE,
          'No se puede verificar que el total coincida con el importe del ERP (tolerancia 0.01 EUR).')
    return results
