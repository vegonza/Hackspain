import os
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from postgrest.exceptions import APIError

from issued import repository
from issued.models import Client, Company, InvoiceInput, IssuedInvoice, Line, Party, totals
from issued.router import issue, router


def sample_invoice(status: str = 'issuing') -> IssuedInvoice:
    return IssuedInvoice(
        id=uuid4(), client_id=uuid4(), status=status,
        invoice_number='F-2026-0001', issue_date=date(2026, 9, 20), due_date=date(2026, 10, 20),
        company=Company(name='Empresa de ejemplo S.L.', tax_id='B12345678', address='Calle Mayor 1, Madrid',
                        email='empresa@example.com', logo_url='', iban='ES00 0000 0000 0000 0000 0000', payment_method='Transferencia bancaria'),
        client=Party(name='Cliente de ejemplo S.L.', tax_id='B87654321', address='Calle del Sol 2, Sevilla', email='cliente@example.com', logo_url=''),
        items=[Line(description='Servicio de consultoría', quantity=Decimal('2'), unit_price=Decimal('100.00'), tax_rate=Decimal('21'))],
        notes='Gracias por su confianza.', base_amount=Decimal('200'), tax_amount=Decimal('42'), total_amount=Decimal('242'),
        pdf_path=None if status == 'issuing' else 'issued/example/invoice.pdf', created_at=datetime.now(timezone.utc), paid_at=None, verifactu_test=None,
    )


class IssuedInvoiceTests(TestCase):
    def setUp(self) -> None:
        environment = patch.dict(os.environ, {'ENV': 'production'})
        environment.start()
        self.addCleanup(environment.stop)
        redis = patch('issued.router.get_redis')
        redis.start()
        self.addCleanup(redis.stop)

    def test_decimal_rounding_per_line_and_mixed_tax_rates(self) -> None:
        items = [Line(description='A', quantity='3', unit_price='0.335', tax_rate='21'),
                 Line(description='B', quantity='2', unit_price='10', tax_rate='10')]
        self.assertEqual(totals(items), (Decimal('21.01'), Decimal('2.21'), Decimal('23.22')))

    def test_due_date_and_line_validation(self) -> None:
        invoice = sample_invoice()
        with self.assertRaises(ValidationError):
            InvoiceInput.model_validate({**invoice.model_dump(), 'due_date': '2026-09-19'})
        for patch_data in [{'quantity': '0'}, {'unit_price': '-1'}, {'tax_rate': '101'}, {'description': ''}]:
            with self.assertRaises(ValidationError):
                Line.model_validate({**invoice.items[0].model_dump(), **patch_data})

    def test_issuance_saves_pdf_before_publishing_income(self) -> None:
        invoice = sample_invoice()
        finished = invoice.model_copy(update={'status': 'issued', 'pdf_path': f'issued/{invoice.id}/invoice.pdf'})
        order: list[str] = []
        with patch('issued.router.repository.reserve_invoice', return_value=invoice), \
             patch('issued.router.render_invoice', return_value=b'%PDF'), \
             patch('issued.router.upload_file', side_effect=lambda *args: order.append('upload')) as upload, \
             patch('issued.router.repository.finish_invoice', side_effect=lambda *args: order.append('finish') or finished):
            result = issue(invoice.id, InvoiceInput.model_validate(invoice.model_dump()))
        self.assertEqual(result.status, 'issued')
        self.assertEqual(order, ['upload', 'finish'])
        upload.assert_called_once_with(f'issued/{invoice.id}/invoice.pdf', b'%PDF', 'application/pdf')

    def test_failed_storage_does_not_publish_and_retry_reuses_reserved_invoice(self) -> None:
        invoice = sample_invoice()
        with patch('issued.router.repository.reserve_invoice', return_value=invoice) as reserve, \
             patch('issued.router.render_invoice', return_value=b'%PDF'), \
             patch('issued.router.upload_file', side_effect=[ConnectionError('storage'), None]), \
             patch('issued.router.repository.finish_invoice', return_value=invoice) as finish:
            with self.assertRaises(ConnectionError):
                issue(invoice.id, InvoiceInput.model_validate(invoice.model_dump()))
            finish.assert_not_called()
            issue(invoice.id, InvoiceInput.model_validate(invoice.model_dump()))
            self.assertEqual(reserve.call_count, 2)
            finish.assert_called_once_with(invoice, f'issued/{invoice.id}/invoice.pdf')

    def test_repeated_issue_does_not_regenerate_or_overwrite_paid_state(self) -> None:
        for status in ('issued', 'paid'):
            invoice = sample_invoice(status)
            with patch('issued.router.repository.reserve_invoice', return_value=invoice), patch('issued.router.upload_file') as upload:
                self.assertEqual(issue(invoice.id, InvoiceInput.model_validate(invoice.model_dump())).status, status)
                upload.assert_not_called()

    def test_pending_pdf_download_is_rejected_and_issued_pdf_is_an_attachment(self) -> None:
        app = FastAPI()
        app.include_router(router)
        invoice = sample_invoice()
        with TestClient(app) as client, patch('issued.router.repository.read_invoice', return_value=invoice):
            self.assertEqual(client.get(f'/api/billing/invoices/{invoice.id}/pdf').status_code, 409)
        invoice = sample_invoice('issued')
        with TestClient(app) as client, patch('issued.router.repository.read_invoice', return_value=invoice), patch('issued.router.download_file', return_value=b'%PDF-example'):
            response = client.get(f'/api/billing/invoices/{invoice.id}/pdf')
            self.assertEqual(response.content, b'%PDF-example')
            self.assertIn('F-2026-0001.pdf', response.headers['content-disposition'])

    def test_api_rejects_invalid_issuance_without_writing(self) -> None:
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client, patch('issued.router.repository.reserve_invoice') as reserve:
            response = client.post(f'/api/billing/invoices/{uuid4()}/issue', json={'items': []})
        self.assertEqual(response.status_code, 422)
        reserve.assert_not_called()

    def test_drafts_cannot_be_saved_through_the_api(self) -> None:
        app = FastAPI()
        app.include_router(router)
        invoice = sample_invoice()
        with TestClient(app) as client, patch('issued.repository.get_client') as database:
            response = client.put(f'/api/billing/invoices/{invoice.id}', json=InvoiceInput.model_validate(invoice.model_dump()).model_dump(mode='json'))
        self.assertEqual(response.status_code, 405)
        database.assert_not_called()

    def test_one_issuance_call_passes_all_input_to_atomic_reservation(self) -> None:
        invoice = sample_invoice()
        data = InvoiceInput.model_validate(invoice.model_dump())
        with patch('issued.repository.get_client') as database:
            database.return_value.rpc.return_value.execute.return_value.data = invoice.model_dump(mode='json')
            self.assertEqual(repository.reserve_invoice(invoice.id, data).invoice_number, invoice.invoice_number)
        database.return_value.rpc.assert_called_once_with('reserve_issued_invoice', {'p_id': str(invoice.id), 'p_invoice': data.model_dump(mode='json')})

    def test_persisted_draft_status_is_not_valid(self) -> None:
        with self.assertRaises(ValidationError):
            IssuedInvoice.model_validate({**sample_invoice().model_dump(), 'status': 'draft'})


class BillingClientTests(TestCase):
    def test_delete_removes_only_the_selected_client_and_returns_no_content(self) -> None:
        app = FastAPI()
        app.include_router(router)
        client_id = uuid4()
        database = MagicMock()
        database.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = [{'name': 'Cliente de ejemplo'}]
        with TestClient(app) as client, patch('issued.repository.get_client', return_value=database):
            response = client.delete(f'/api/billing/clients/{client_id}')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')
        database.table.assert_called_once_with('billing_clients')
        database.table.return_value.delete.return_value.eq.assert_called_once_with('id', str(client_id))

    def test_delete_preserves_clients_linked_to_invoices(self) -> None:
        app = FastAPI()
        app.include_router(router)
        database = MagicMock()
        database.table.return_value.delete.return_value.eq.return_value.execute.side_effect = APIError({
            'code': '23503', 'message': 'foreign key violation', 'details': None, 'hint': None,
        })
        with TestClient(app) as client, patch('issued.repository.get_client', return_value=database):
            response = client.delete(f'/api/billing/clients/{uuid4()}')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['detail'], 'billing_client_has_invoices')
        database.table.assert_called_once_with('billing_clients')

    def test_delete_missing_client_returns_not_found(self) -> None:
        database = MagicMock()
        database.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
        with patch('issued.repository.get_client', return_value=database), self.assertRaises(HTTPException) as error:
            repository.delete_client(uuid4())
        self.assertEqual(error.exception.status_code, 404)

    def test_client_update_only_changes_directory_not_invoice_snapshots(self) -> None:
        invoice = sample_invoice('issued')
        client = Client(id=invoice.client_id, **invoice.client.model_dump())
        client.name = 'Nombre actualizado'
        database = MagicMock()
        database.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [client.model_dump(mode='json')]
        with patch('issued.repository.get_client', return_value=database):
            updated = repository.update_client(client.id, Party.model_validate(client.model_dump()))
        self.assertEqual(updated.name, 'Nombre actualizado')
        database.table.assert_called_once_with('billing_clients')
        database.table.return_value.update.assert_called_once_with(Party.model_validate(client.model_dump()).model_dump())

    def test_update_missing_client_is_not_an_insert(self) -> None:
        database = MagicMock()
        database.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
        with patch('issued.repository.get_client', return_value=database):
            with self.assertRaises(HTTPException) as error:
                repository.update_client(uuid4(), sample_invoice().client)
        self.assertEqual(error.exception.status_code, 404)
        database.table.return_value.insert.assert_not_called()


class IssuedInvoiceListTests(TestCase):
    def test_list_selects_summary_columns_and_omits_receipts(self) -> None:
        invoice = sample_invoice('issued').model_dump(mode='json')
        invoice['verifactu_test'] = {'qr_code': 'x' * 240000}
        database = MagicMock()
        query = database.table.return_value.select.return_value.order.return_value.order.return_value
        query.range.return_value.execute.return_value.data = [invoice]
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client, patch('issued.repository.get_client', return_value=database):
            response = client.get('/api/billing/invoices')
        self.assertEqual(response.status_code, 200)
        summary = response.json()[0]
        self.assertEqual(summary['invoice_number'], invoice['invoice_number'])
        self.assertEqual(summary['items'], invoice['items'])
        self.assertEqual(summary['base_amount'], invoice['base_amount'])
        self.assertNotIn('verifactu_test', summary)
        self.assertNotIn('company', summary)
        self.assertNotIn('notes', summary)
        self.assertLess(len(response.content), 2000)
        selected = database.table.return_value.select.call_args.args[0].split(',')
        self.assertEqual(set(selected), set(summary))

    def test_list_reads_every_page_without_selecting_receipts(self) -> None:
        invoice = sample_invoice('issued').model_dump(mode='json')
        database = MagicMock()
        query = database.table.return_value.select.return_value.order.return_value.order.return_value
        query.range.return_value.execute.side_effect = [MagicMock(data=[invoice] * 1000), MagicMock(data=[invoice])]
        with patch('issued.repository.get_client', return_value=database):
            result = repository.list_invoices()
        self.assertEqual(len(result), 1001)
        self.assertEqual([call.args for call in query.range.call_args_list], [(0, 999), (1000, 1999)])

    def test_missing_client_rejection_happens_before_pdf_or_submission(self) -> None:
        app = FastAPI()
        app.include_router(router)
        invoice = sample_invoice()
        database = MagicMock()
        database.rpc.return_value.execute.side_effect = APIError({
            'code': 'P0002', 'message': 'query returned no rows', 'details': None, 'hint': None,
        })
        with TestClient(app) as client, patch('issued.router.get_redis'), \
             patch('issued.repository.get_client', return_value=database), \
             patch('issued.router.submit_test') as submit, patch('issued.router.upload_file') as upload:
            response = client.post(f'/api/billing/invoices/{invoice.id}/issue',
                                   json=InvoiceInput.model_validate(invoice.model_dump()).model_dump(mode='json'))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['detail'], 'billing_client_not_found')
        submit.assert_not_called()
        upload.assert_not_called()
