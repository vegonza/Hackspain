import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from erp.models import ErpEntryDetail
from erp.router import router as erp_router
from shared.usage import UsageRecord, save_usage


class InvoiceContractTests(unittest.TestCase):
    def test_usage_exposes_invoice_names_but_preserves_storage_columns(self) -> None:
        record = UsageRecord.model_validate({
            'provider': 'Mistral', 'model': 'ocr', 'operation': 'ocr',
            'document_id': str(uuid4()), 'document_name': 'factura.pdf', 'usage': [],
        })
        payload = record.model_dump(mode='json')
        self.assertEqual(payload['invoice_name'], 'factura.pdf')
        self.assertNotIn('document_id', payload)
        self.assertIn('invoice_id', UsageRecord.model_json_schema(mode='serialization')['properties'])
        with patch('shared.usage.get_client') as client:
            save_usage(record)
        saved = client.return_value.table.return_value.upsert.call_args.args[0]
        self.assertEqual(saved['document_id'], record.invoice_id)
        self.assertEqual(saved['document_name'], record.invoice_name)
        self.assertNotIn('invoice_id', saved)
        self.assertEqual(UsageRecord.model_validate(saved), record)

    def test_erp_http_response_exposes_linked_invoices_from_the_existing_rpc(self) -> None:
        identifier = uuid4()
        linked = {'id': str(uuid4()), 'name': 'factura.pdf'}
        entry = ErpEntryDetail.model_validate({
            'id': identifier, 'entry_id': 'AS-1', 'supplier_id': 'P1', 'tax_id': 'B1',
            'order_id': 'PO-1', 'status': 'PENDIENTE', 'raw_date': '', 'raw_amount': '',
            'documents': [linked],
        })
        app = FastAPI()
        app.include_router(erp_router)
        with patch('erp.router.read_entry', return_value=entry), TestClient(app) as client:
            response = client.get(f'/api/erp/entries/{identifier}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['invoices'], [linked])
        self.assertNotIn('documents', response.json())
