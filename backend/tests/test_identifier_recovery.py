import unittest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from extractor.extraction import InvoiceExtraction, InvoiceLine
from extractor.recovery import recover_identifiers
from rules.evaluator import evaluate_rules, payment_decision
from rules.models import RuleContext
from suppliers.models import Supplier
from orders.models import Order
from erp import ErpEntry


class IdentifierRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.supplier = Supplier(supplier_id='P1', legal_name='Proveedor', tax_id='B98120774',
                                 iban='ES4414650100951704302211', city='Málaga', payment_terms_days=30)
        self.invoice = InvoiceExtraction(
            invoice_number='F1', supplier_name='Proveedor', supplier_nif=self.supplier.tax_id,
            iban=self.supplier.iban, invoice_date='2026-01-01', purchase_order='PO-1', currency='EUR',
            line_items=[InvoiceLine(description='Servicio', amount='100')],
            tax_base='100', vat_rate='21', vat_amount='21', total='121', notes=[], uncertainties=[],
        )

    def test_recovers_either_field_without_mutating_original(self) -> None:
        for field, original, expected, anchor in (
            ('iban', 'ES4414650100981704302211', self.supplier.iban, 'supplier_nif'),
            ('supplier_nif', 'B96120774', self.supplier.tax_id, 'iban'),
        ):
            with self.subTest(field=field):
                invoice = self.invoice.model_copy(update={field: original})
                recovered, corrections = recover_identifiers(invoice, [self.supplier])
                self.assertEqual(getattr(recovered, field), expected)
                self.assertEqual(getattr(invoice, field), original)
                self.assertEqual(len(corrections), 1)
                self.assertEqual(corrections[0].model_dump(), {
                    'field': field, 'original': original, 'corrected': expected,
                    'supplier_id': 'P1', 'matched_field': anchor, 'matched_value': getattr(self.invoice, anchor),
                })

    def test_does_not_recover_two_errors_missing_fields_or_different_lengths(self) -> None:
        for changes in (
            {'iban': 'ES4414650100981704302212'},
            {'iban': 'ES441465010095170430221'},
            {'iban': 'ES44146501009517043022111'},
            {'supplier_nif': 'B96120775'},
            {'supplier_nif': 'B9812077'},
            {'iban': ''}, {'supplier_nif': ''},
            {'iban': 'ES4414650100981704302211', 'supplier_nif': 'B96120774'},
        ):
            with self.subTest(changes=changes):
                invoice = self.invoice.model_copy(update=changes)
                recovered, corrections = recover_identifiers(invoice, [self.supplier])
                self.assertEqual(recovered, invoice)
                self.assertEqual(corrections, [])

    def test_ambiguous_anchor_is_not_disambiguated_by_fuzzy_field(self) -> None:
        for field, value, other in (
            ('supplier_nif', 'B96120774', self.supplier.model_copy(update={'supplier_id': 'P2', 'tax_id': 'A12345678'})),
            ('iban', 'ES4414650100981704302211', self.supplier.model_copy(update={'supplier_id': 'P2', 'iban': 'ES001234'})),
        ):
            with self.subTest(field=field):
                invoice = self.invoice.model_copy(update={field: value})
                recovered, corrections = recover_identifiers(invoice, [self.supplier, other])
                self.assertEqual(recovered, invoice)
                self.assertEqual(corrections, [])

    def test_exact_or_unknown_identity_does_not_create_corrections(self) -> None:
        for suppliers in ([self.supplier], []):
            recovered, corrections = recover_identifiers(self.invoice, suppliers)
            self.assertEqual(recovered, self.invoice)
            self.assertEqual(corrections, [])

    def test_formatting_is_normalized_but_original_evidence_is_preserved(self) -> None:
        invoice = self.invoice.model_copy(update={'supplier_nif': ' b-98120774 ', 'iban': 'es44 1465 0100 9817 0430 2211'})
        recovered, corrections = recover_identifiers(invoice, [self.supplier])
        self.assertEqual(recovered.iban, self.supplier.iban)
        self.assertEqual(corrections[0].original, invoice.iban)
        self.assertEqual(corrections[0].matched_value, self.supplier.tax_id)

    def test_recovery_preserves_other_payment_checks(self) -> None:
        invoice_id = uuid4()
        invoice, _ = recover_identifiers(
            self.invoice.model_copy(update={'supplier_nif': 'B96120774'}), [self.supplier],
        )
        context = RuleContext(
            invoice=invoice, invoice_id=invoice_id, claimed_by_invoice_id=invoice_id,
            evaluation_date=date(2026, 9, 20), supplier=self.supplier,
            order=Order(order_id='PO-1', supplier_id='P1', tax_id=self.supplier.tax_id,
                        amount=Decimal('121'), status='ABIERTO', date=date(2026, 1, 1)),
            entries=[ErpEntry(entry_id='AS-1', supplier_id='P1', tax_id=self.supplier.tax_id,
                              order_id='PO-1', amount=Decimal('121'), raw_amount='121,00',
                              status='PENDIENTE', raw_date='01/01/2026')],
        )
        self.assertEqual(payment_decision(evaluate_rules(context), [], []).classification, 'PAGAR')
        context.order.amount = Decimal('120')
        self.assertEqual(payment_decision(evaluate_rules(context), [], []).classification, 'ESCALAR')
        context.entries[0].status = 'PAGADA'
        self.assertEqual(payment_decision(evaluate_rules(context), [], []).classification, 'NO_PAGAR')

    def test_notes_and_uncertainties_are_not_discarded(self) -> None:
        invoice = self.invoice.model_copy(update={
            'iban': 'ES4414650100981704302211', 'notes': ['Factura anulada'],
            'uncertainties': ['Fecha ilegible'],
        })
        recovered, _ = recover_identifiers(invoice, [self.supplier])
        self.assertEqual(recovered.notes, invoice.notes)
        self.assertEqual(recovered.uncertainties, invoice.uncertainties)
