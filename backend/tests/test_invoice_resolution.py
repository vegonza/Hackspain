from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from invoices.router import router


class InvoiceResolutionTests(TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.invoice_id = uuid4()
        self.path = f'/api/invoices/{self.invoice_id}/resolve'

    def test_resolves_both_choices_and_retains_review_history(self) -> None:
        for classification in ('PAGAR', 'NO_PAGAR'):
            with self.subTest(classification=classification):
                decision = {
                    'classification': classification, 'reasons': ['Resuelta manualmente'],
                    'checks': {'amount': False},
                    'resolution': {'resolved_at': '2026-09-20T12:00:00Z', 'previous_reasons': ['Revisar importe']},
                }
                database = MagicMock()
                database.rpc.return_value.execute.return_value.data = {'name': 'FA-123.pdf', 'decision': decision}
                with patch('invoices.resolution.get_client', return_value=database):
                    response = self.client.post(self.path, json={'classification': classification})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['classification'], classification)
                self.assertEqual(response.json()['resolution'], decision['resolution'])
                self.assertEqual(response.json()['checks'], {'amount': False})
                database.rpc.assert_called_once_with('resolve_invoice_decision', {
                    'p_document_id': str(self.invoice_id), 'p_classification': classification,
                })

    def test_stale_review_duplicate_and_missing_identity_are_conflicts(self) -> None:
        for message in ('invoice_not_reviewable', 'invoice_duplicate_payment', 'invoice_identity_required'):
            with self.subTest(message=message), patch('invoices.resolution.get_client') as database:
                database.return_value.rpc.return_value.execute.side_effect = APIError({
                    'code': 'P0001', 'message': message, 'details': None, 'hint': None,
                })
                response = self.client.post(self.path, json={'classification': 'PAGAR'})
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()['detail'], message)

    def test_cannot_resolve_to_escalar_or_an_arbitrary_classification(self) -> None:
        with patch('invoices.resolution.get_client') as database:
            for classification in ('ESCALAR', 'PAID', '', None):
                response = self.client.post(self.path, json={'classification': classification})
                self.assertEqual(response.status_code, 422)
            database.assert_not_called()

    def test_database_failure_is_not_reported_as_a_successful_resolution(self) -> None:
        with patch('invoices.resolution.get_client') as database:
            database.return_value.rpc.return_value.execute.side_effect = APIError({
                'code': '08006', 'message': 'Connection failed', 'details': None, 'hint': None,
            })
            with self.assertRaises(APIError):
                self.client.post(self.path, json={'classification': 'NO_PAGAR'})
