from rules.models import RuleContext, RuleResult
from shared.identifiers import compact_identifier, order_key


def identity_rules(context: RuleContext) -> list[RuleResult]:
    invoice = context.invoice
    nif = compact_identifier(invoice.supplier_nif)
    supplier, order, entries = context.supplier, context.order, context.entries
    results: list[RuleResult] = []

    def check(rule: str, passed: bool, reason: str) -> None:
        results.append(RuleResult(rule=rule, passed=passed, reason=reason))

    check('supplier', supplier is not None and bool(nif) and supplier.tax_id == nif,
          'No se encuentra el proveedor del pedido o su NIF no coincide con la factura.')
    check('iban', supplier is not None and bool(invoice.iban.strip()) and compact_identifier(invoice.iban) == supplier.iban,
          'El IBAN no coincide con el del proveedor del maestro o no se puede verificar.')
    check('order', order is not None and not context.order_ambiguous and order_key(order.order_id) == order_key(invoice.purchase_order),
          'El pedido no existe o su código es ambiguo en el maestro.')
    check('order_supplier', order is not None and supplier is not None and order.supplier_id == supplier.supplier_id
          and (order.tax_id is None or order.tax_id == nif),
          'El proveedor o NIF registrado en el pedido no coincide con la factura.')
    check('erp_unique', len(entries) == 1, 'El pedido no tiene un asiento ERP único.')
    check('erp_supplier', len(entries) == 1 and supplier is not None and entries[0].supplier_id == supplier.supplier_id
          and compact_identifier(entries[0].tax_id) == nif,
          'El proveedor o NIF del ERP no coincide con la factura o no se puede verificar.')
    check('erp_pending', len(entries) == 1 and entries[0].status == 'PENDIENTE',
          'El pedido no tiene un único asiento PENDIENTE en el ERP.')
    check('not_paid', not any(entry.status == 'PAGADA' for entry in entries),
          'El ERP registra el pedido como PAGADA; nunca pagar dos veces.')
    return results
