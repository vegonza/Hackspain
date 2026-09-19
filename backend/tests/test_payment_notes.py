import unittest
from datetime import date
from decimal import Decimal
from uuid import UUID
from unittest.mock import patch

from documents.classification import classify_document
from rules.models import ResolvedReferences
from suppliers.models import Supplier
from orders.models import Order
from erp import ErpEntry
from pipeline.extraction_3.extraction import InvoiceExtraction, InvoiceLine
from documents.payment_notes import PaymentConcern, PaymentNotesReview, SourcedPaymentConcern, SourcedPaymentNotesReview, review_payment_notes


class PaymentNotesTests(unittest.TestCase):
    def test_rejects_evidence_not_present_in_invoice(self) -> None:
        review = SourcedPaymentNotesReview(concerns=[SourcedPaymentConcern(note_index=1, reason="Anulación")])
        with patch("documents.payment_notes.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = review
            with self.assertRaisesRegex(ValueError, "evidence is absent"):
                review_payment_notes(["Condiciones de pago: 30 días."], {})

    def test_rejects_empty_evidence(self) -> None:
        review = SourcedPaymentNotesReview(concerns=[SourcedPaymentConcern(note_index=0, reason="Anulación")])
        with patch("documents.payment_notes.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = review
            with self.assertRaisesRegex(ValueError, "evidence is absent"):
                review_payment_notes([""], {})

    def test_keeps_grounded_concern_with_conflicting_payment_terms(self) -> None:
        review = SourcedPaymentNotesReview(concerns=[SourcedPaymentConcern(note_index=0, reason="Requiere revisión")])
        with patch("documents.payment_notes.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = review
            result = review_payment_notes(["Pago a 30 días. Pedido anulado."], {})
        self.assertEqual(result.concerns[0].evidence, "Pago a 30 días. Pedido anulado.")


class PaymentPolicyTests(unittest.TestCase):
    def test_payment_restriction_escalates_but_never_overrides_paid_erp(self) -> None:
        invoice = InvoiceExtraction(
            invoice_number="INV-1", supplier_name="Proveedor", supplier_nif="B12345678",
            iban="ES123", invoice_date="2026-01-01", purchase_order="PO-2026-0001",
            line_items=[InvoiceLine(description="Servicio", amount="100")],
            tax_base="100", vat_rate="21", vat_amount="21", total="121",
            notes=["Pedido anulado."], uncertainties=[],
        )
        entry = ErpEntry(entry_id="AS-1", order_id=invoice.purchase_order, supplier_id="P1", tax_id=invoice.supplier_nif,
                         raw_amount="121,00", amount=Decimal("121"), status="PENDIENTE", raw_date="01/01/2026")
        review = PaymentNotesReview(concerns=[PaymentConcern(evidence="Pedido anulado.", reason="Anulación")])
        references = ResolvedReferences(
            supplier=Supplier(supplier_id='P1', legal_name='Proveedor', tax_id=invoice.supplier_nif,
                              iban=invoice.iban, city='Málaga', payment_terms_days=30),
            order=Order(order_id=invoice.purchase_order, supplier_id='P1', tax_id=invoice.supplier_nif,
                        amount=Decimal('121'), status='ABIERTO', date=date(2026, 1, 1)),
            entries=[entry],
        )
        document_id = UUID('00000000-0000-0000-0000-000000000001')
        with patch('documents.classification.resolve_references', return_value=references), \
                patch('documents.classification.review_payment_notes', return_value=review) as assess:
            decision = classify_document(document_id, invoice, date(2026, 9, 19), pending_review=set(), duplicate_order=False)
            self.assertEqual(decision.classification, 'ESCALAR')
            self.assertFalse(decision.checks['payment_notes'])
            self.assertTrue(all(passed for name, passed in decision.checks.items() if name != 'payment_notes'))
            self.assertIn('Pedido anulado.', decision.reasons[0])
            assess.reset_mock()
            entry.status = 'PAGADA'
            decision = classify_document(document_id, invoice, date(2026, 9, 19), pending_review=set(), duplicate_order=False)
            self.assertEqual(decision.classification, 'NO_PAGAR')
            assess.assert_not_called()


if __name__ == "__main__":
    unittest.main()
