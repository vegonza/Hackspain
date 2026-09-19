import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from uuid import UUID

from invoices.classification import classify_invoice
from rules.models import Decision, ResolvedReferences
from suppliers.models import Supplier
from orders.models import Order
from extractor.extraction import InvoiceExtraction, InvoiceLine
from invoices.payment_notes import PaymentConcern, PaymentNotesReview
from erp import ErpEntry


class ClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.invoice_id = UUID('00000000-0000-0000-0000-000000000001')
        self.references = ResolvedReferences(
            supplier=Supplier(supplier_id='NEW', legal_name='Proveedor Nuevo', tax_id='B12345678',
                              iban='ES001234', city='Málaga', payment_terms_days=30),
            order=Order(order_id='PO-2026-9999', supplier_id='NEW', tax_id='B12345678',
                        amount=Decimal('121'), status='ABIERTO', date=date(2026, 9, 1)),
            entries=[ErpEntry(entry_id='AS-NEW', order_id='PO-2026-9999', supplier_id='NEW', tax_id='B12345678',
                              raw_amount='121,00', amount=Decimal('121'), status='PENDIENTE', raw_date='01/09/2026')],
        )
        claim = patch('invoices.classification.claim_order', return_value=self.invoice_id)
        self.claim = claim.start()
        self.addCleanup(claim.stop)
        resolver = patch('invoices.classification.resolve_references', return_value=self.references)
        self.resolver = resolver.start()
        self.addCleanup(resolver.stop)
        self.invoice = InvoiceExtraction(
            invoice_number="NEW-1", supplier_name="Proveedor Nuevo", supplier_nif="B12345678",
            iban="ES001234", invoice_date="2026-09-01", purchase_order="PO-2026-9999", currency="EUR",
            line_items=[InvoiceLine(description="Servicio", amount="100.00")],
            tax_base="100.00", vat_rate="21", vat_amount="21.00", total="121.00",
            notes=[], uncertainties=[],
        )
        self.notes = patch("invoices.classification.review_payment_notes", return_value=PaymentNotesReview(concerns=[]))
        self.review = self.notes.start()
        self.addCleanup(self.notes.stop)

    def classify(self, invoice: InvoiceExtraction) -> Decision:
        return classify_invoice(self.invoice_id, invoice, date(2026, 9, 19))

    def test_loads_supabase_references_for_invoice(self) -> None:
        self.classify(self.invoice)
        self.resolver.assert_called_once_with(self.invoice_id, self.invoice.purchase_order)

    def test_lookup_failure_propagates_without_local_data(self) -> None:
        self.resolver.side_effect = RuntimeError('Supabase unavailable')
        with self.assertRaisesRegex(RuntimeError, 'Supabase unavailable'):
            self.classify(self.invoice)
        self.review.assert_not_called()

    def test_new_supplier_and_order_pay_without_dataset_identifiers(self) -> None:
        self.assertEqual(self.classify(self.invoice).classification, "PAGAR")

    def test_invalid_fields_escalate(self) -> None:
        cases = [
            {"supplier_nif": "B87654321"}, {"iban": "ES009999"},
            {"purchase_order": "PO-2026-9998"}, {"total": "122.00"},
            {"vat_amount": "22.00"}, {"invoice_date": "2026-09-20"},
            {"invoice_date": "2026-02-30"}, {"tax_base": ""},
            {"total": "NaN"}, {"line_items": []},
            {"uncertainties": ["Identificador ilegible"]},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.classify(self.invoice.model_copy(update=changes)).classification, "ESCALAR")

    def test_cent_tolerance_boundary(self) -> None:
        self.assertEqual(self.classify(self.invoice.model_copy(update={"total": "121.01"})).classification, "PAGAR")
        self.assertEqual(self.classify(self.invoice.model_copy(update={"total": "121.02"})).classification, "ESCALAR")

    def test_pending_review_and_other_claim_escalate(self) -> None:
        self.claim.return_value = UUID("00000000-0000-0000-0000-000000000002")
        self.assertEqual(self.classify(self.invoice).classification, "ESCALAR")
        self.claim.return_value = self.invoice_id
        self.references.order.review_required = True
        self.assertEqual(self.classify(self.invoice).classification, "ESCALAR")

    def test_conflicted_order_without_owner_escalates(self) -> None:
        self.claim.return_value = None
        decision = self.classify(self.invoice)
        self.assertEqual(decision.classification, 'ESCALAR')
        self.assertFalse(decision.checks['order_claim'])
        self.references.entries[0].status = 'PAGADA'
        self.assertEqual(self.classify(self.invoice).classification, 'NO_PAGAR')

    def test_paid_prevents_payment_even_with_other_anomalies(self) -> None:
        self.references.entries[0].status = "PAGADA"
        invoice = self.invoice.model_copy(update={"iban": "WRONG"})
        self.assertEqual(self.classify(invoice).classification, "NO_PAGAR")
        self.review.assert_not_called()

    def test_erp_and_order_supplier_checks(self) -> None:
        self.references.entries[0].tax_id = "B87654321"
        self.assertEqual(self.classify(self.invoice).classification, "ESCALAR")
        self.references.entries[0].tax_id = "B12345678"
        self.references.order.supplier_id = "OTHER"
        self.assertEqual(self.classify(self.invoice).classification, "ESCALAR")

    def test_commercial_hold_escalates_with_valid_arithmetic(self) -> None:
        self.review.return_value = PaymentNotesReview(concerns=[PaymentConcern(
            evidence="Factura anulada", reason="La factura está anulada.",
        )])
        invoice = self.invoice.model_copy(update={"notes": ["Factura anulada"]})
        decision = self.classify(invoice)
        self.assertEqual(decision.classification, "ESCALAR")
        self.assertIn("Factura anulada", decision.reasons[0])

    def test_uses_client_normalized_amount_and_rejects_unreadable_amount(self) -> None:
        self.references.entries[0].raw_amount = "121.00"
        self.assertEqual(self.classify(self.invoice).classification, "PAGAR")
        self.references.entries[0].amount = None
        result = self.classify(self.invoice)
        self.assertEqual(result.classification, "ESCALAR")
        self.assertFalse(result.checks["erp_amount"])
