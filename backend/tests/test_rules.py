import unittest
from datetime import date
from decimal import Decimal

from erp import ErpEntry
from orders.models import Order
from pipeline.extraction_3.extraction import InvoiceExtraction, InvoiceLine
from rules.evaluator import evaluate_rules, payment_decision
from rules.models import RuleContext
from suppliers.models import Supplier


class RulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = RuleContext(
            invoice=InvoiceExtraction(
                invoice_number='F-1', supplier_name='Proveedor', supplier_nif='B12345678', iban='ES001234',
                invoice_date='2026-09-01', purchase_order='PO-1',
                line_items=[InvoiceLine(description='Servicio', amount='100')],
                tax_base='100', vat_rate='21', vat_amount='21', total='121', notes=[], uncertainties=[],
            ),
            supplier=Supplier(supplier_id='P1', legal_name='Proveedor', tax_id='B12345678', iban='ES001234',
                                city='Málaga', payment_terms_days=30),
            order=Order(order_id='PO-1', supplier_id='P1', tax_id='B12345678', amount=Decimal('121'),
                          status='ABIERTO', date=date(2026, 9, 1)),
            entries=[ErpEntry(entry_id='AS-1', supplier_id='P1', tax_id='B12345678', order_id='PO-1',
                              status='PENDIENTE', raw_date='01/09/2026', raw_amount='121,00', amount=Decimal('121'))],
            evaluation_date=date(2026, 9, 19),
        )

    def classification(self) -> str:
        return payment_decision(evaluate_rules(self.context), self.context.invoice.notes, None).classification

    def test_valid_invoice_passes_without_external_services(self) -> None:
        self.assertEqual(self.classification(), 'PAGAR')

    def test_missing_order_nif_uses_supplier_relationship(self) -> None:
        self.context.order.tax_id = None
        self.assertEqual(self.classification(), 'PAGAR')
        self.context.order.supplier_id = 'OTHER'
        self.assertEqual(self.classification(), 'ESCALAR')

    def test_conflicting_order_nif_escalates(self) -> None:
        self.context.order.tax_id = 'OTHER'
        self.assertEqual(self.classification(), 'ESCALAR')

    def test_unreviewed_notes_escalate(self) -> None:
        self.context.invoice.notes = ['Pedido anulado.']
        self.assertEqual(self.classification(), 'ESCALAR')

    def test_any_paid_entry_vetoes_payment_even_with_multiple_matches(self) -> None:
        self.context.entries.append(self.context.entries[0].model_copy(update={'entry_id': 'AS-2', 'status': 'PAGADA'}))
        self.assertEqual(self.classification(), 'NO_PAGAR')

    def test_amount_tolerance_and_nonfinite_lines(self) -> None:
        self.context.invoice.total = '121.01'
        self.assertEqual(self.classification(), 'PAGAR')
        self.context.invoice.total = '121.02'
        self.assertEqual(self.classification(), 'ESCALAR')
        self.context.invoice.total = '121'
        for amount in ('NaN', 'Infinity', ''):
            with self.subTest(amount=amount):
                self.context.invoice.line_items[0].amount = amount
                self.assertEqual(self.classification(), 'ESCALAR')

    def test_future_invalid_and_current_dates(self) -> None:
        for day in ('2026-09-20', '2026-02-30', ''):
            self.context.invoice.invoice_date = day
            self.assertEqual(self.classification(), 'ESCALAR')
        self.context.invoice.invoice_date = '2026-09-19'
        self.assertEqual(self.classification(), 'PAGAR')

    def test_missing_or_ambiguous_erp_escalates(self) -> None:
        self.context.entries *= 2
        self.assertEqual(self.classification(), 'ESCALAR')
        self.context.entries = []
        self.assertEqual(self.classification(), 'ESCALAR')
