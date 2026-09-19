import unittest
from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from documents.repository import DocumentDetails
from pipeline.classification import process
from pipeline.extraction_3.extraction import InvoiceExtraction
from rules.models import Decision


class PipelineClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = DocumentDetails(id=uuid4(), name='Factura.pdf', sha256='a' * 64,
                                        created_at=datetime.now(timezone.utc), stages=[])
        self.invoice = InvoiceExtraction(
            invoice_number='F1', supplier_name='Proveedor', supplier_nif='B12345678', iban='ES001234',
            invoice_date='2026-01-01', purchase_order=' po-001 ', line_items=[], tax_base='100', vat_rate='21',
            vat_amount='21', total='121', notes=[], uncertainties=[],
        )
        self.candidate = Decision(classification='PAGAR', reasons=['Verificada'], checks={'order_claim': True})

    def test_publishes_and_keeps_the_classifiers_decision(self) -> None:
        client = MagicMock()
        client.rpc.return_value.execute.return_value.data = self.candidate.model_dump(mode='json')
        with (
            patch('pipeline.classification.download_file', return_value=self.invoice.model_dump_json().encode()),
            patch('pipeline.classification.classify_document', return_value=self.candidate),
            patch('pipeline.classification.track_usage', return_value=nullcontext(None)),
            patch('pipeline.classification.get_client', return_value=client),
        ):
            process(self.document)
        self.assertEqual(self.document.payment_decision, self.candidate)
        client.rpc.assert_called_once_with('publish_payment_decision', {
            'p_document_id': str(self.document.id), 'p_order_key': 'PO-001',
            'p_decision': self.candidate.model_dump(mode='json'),
        })

    def test_retry_with_saved_decision_does_not_repeat_ai_call(self) -> None:
        self.document.payment_decision = self.candidate
        with patch('pipeline.classification.classify_document') as classify, patch('pipeline.classification.get_client') as client:
            process(self.document)
        classify.assert_not_called()
        client.assert_not_called()

    def test_publication_failure_remains_retryable(self) -> None:
        client = MagicMock()
        client.rpc.return_value.execute.side_effect = RuntimeError('Database unavailable')
        with (
            patch('pipeline.classification.download_file', return_value=self.invoice.model_dump_json().encode()),
            patch('pipeline.classification.classify_document', return_value=self.candidate),
            patch('pipeline.classification.track_usage', return_value=nullcontext(None)),
            patch('pipeline.classification.get_client', return_value=client),
        ):
            with self.assertRaisesRegex(RuntimeError, 'Database unavailable'):
                process(self.document)
        self.assertIsNone(self.document.payment_decision)

    def test_rules_claim_lookup_and_publication_work_together(self) -> None:
        from pipeline.extraction_3.extraction import InvoiceLine
        from documents.payment_notes import PaymentNotesReview

        self.invoice.purchase_order = 'PO-001'
        self.invoice.line_items = [InvoiceLine(description='Servicio', amount='100')]
        other_id = uuid4()
        for owner, status, expected in (
            (self.document.id, 'PENDIENTE', 'PAGAR'),
            (other_id, 'PENDIENTE', 'ESCALAR'),
            (other_id, 'PAGADA', 'NO_PAGAR'),
        ):
            with self.subTest(owner=owner, status=status):
                self.document.payment_decision = None
                client = MagicMock()

                def rpc(name: str, args: dict[str, object]) -> MagicMock:
                    response = MagicMock()
                    if name == 'claim_invoice_order':
                        response.execute.return_value.data = str(owner)
                    elif name == 'get_rule_references':
                        response.execute.return_value.data = {
                            'supplier': {'supplier_id': 'P1', 'legal_name': 'Proveedor', 'tax_id': 'B12345678',
                                         'iban': 'ES001234', 'city': 'Málaga', 'payment_terms_days': 30},
                            'order': {'order_id': 'PO-001', 'supplier_id': 'P1', 'tax_id': 'B12345678',
                                      'amount': '121', 'status': 'ABIERTO', 'date': '2026-01-01', 'review_required': False},
                            'entries': [{'entry_id': 'AS-1', 'supplier_id': 'P1', 'tax_id': 'B12345678',
                                         'order_id': 'PO-001', 'status': status, 'raw_date': '01/01/2026',
                                         'raw_amount': '121,00', 'amount': '121'}],
                        }
                    elif name == 'publish_payment_decision':
                        response.execute.return_value.data = args['p_decision']
                    else:
                        self.fail(f'Unexpected RPC: {name}')
                    return response

                client.rpc.side_effect = rpc
                with (
                    patch('pipeline.classification.download_file', return_value=self.invoice.model_dump_json().encode()),
                    patch('pipeline.classification.track_usage', return_value=nullcontext(None)),
                    patch('pipeline.classification.get_client', return_value=client),
                    patch('rules.resolver.get_client', return_value=client),
                    patch('documents.classification.review_payment_notes', return_value=PaymentNotesReview(concerns=[])) as notes,
                ):
                    process(self.document)
                self.assertEqual(self.document.payment_decision.classification, expected)
                self.assertEqual(self.document.payment_decision.claimed_by_document_id, owner)
                self.assertEqual([call.args[0] for call in client.rpc.call_args_list],
                                 ['claim_invoice_order', 'get_rule_references', 'publish_payment_decision'])
                if status == 'PAGADA':
                    notes.assert_not_called()
