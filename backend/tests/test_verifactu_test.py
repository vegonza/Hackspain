import os
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from issued.models import InvoiceInput, IssuedInvoice, Line, TestTaxParties, TestTaxParty, VerifactuTestReceipt
from issued.router import issue, router, verifactu_test
from issued.verifactu import TEST_ENDPOINT, submit_test
from tests.test_issued_invoices import sample_invoice


def accepted_receipt() -> VerifactuTestReceipt:
    return VerifactuTestReceipt(
        parties=TestTaxParties(issuer=TestTaxParty(name='Test issuer', tax_id='B12959755'),
                               client=TestTaxParty(name='Test client', tax_id='B44531218')),
        qr_code='data:image/bmp;base64,bitmap', csv='TEST-CSV', submitted_at=datetime.now(timezone.utc), pdf_path=None,
    )


class VerifactuSandboxTests(TestCase):
    def setUp(self) -> None:
        environment = patch.dict(os.environ, {
            'VERIFACTU_TEST_SELLER_NAME': 'Test issuer', 'VERIFACTU_TEST_SELLER_ID': 'B12959755',
            'VERIFACTU_TEST_BUYER_NAME': 'Test client', 'VERIFACTU_TEST_BUYER_ID': 'B44531218',
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_only_sandbox_receives_payload_and_tax_matches_invoice_rounding(self) -> None:
        invoice = sample_invoice('issued')
        invoice.items = [Line(description='A', quantity='3', unit_price='0.335', tax_rate='21'),
                         Line(description='B', quantity='1', unit_price='20', tax_rate='10')]
        response = MagicMock()
        response.json.return_value = {'Return': {'StatusResponse': 'Correcto', 'QrCode': 'bitmap', 'CSV': 'TEST-CSV'}}
        with patch.dict(os.environ, {'ENV': 'test', 'VERIFACTU_SERVICE_KEY': 'test-key'}), patch('issued.verifactu.httpx.post', return_value=response) as post:
            receipt = submit_test(invoice)
            self.assertEqual(receipt.qr_code, 'data:image/bmp;base64,bitmap')
            self.assertEqual(receipt.csv, 'TEST-CSV')
            self.assertEqual(receipt.parties.issuer.tax_id, 'B12959755')
            self.assertEqual(receipt.parties.client.tax_id, 'B44531218')
        self.assertEqual(post.call_args.args, (TEST_ENDPOINT,))
        self.assertFalse(post.call_args.kwargs['follow_redirects'])
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['TaxItems'], [
            {'TaxScheme': '01', 'TaxType': 'S1', 'TaxRate': 21.0, 'TaxBase': 1.01, 'TaxAmount': .21},
            {'TaxScheme': '01', 'TaxType': 'S1', 'TaxRate': 10.0, 'TaxBase': 20.0, 'TaxAmount': 2.0},
        ])
        self.assertEqual(payload['SellerID'], 'B12959755')
        self.assertEqual(payload['CompanyName'], 'Test issuer')
        self.assertEqual(invoice.company.tax_id, 'B12345678')
        self.assertEqual(payload['InvoiceID'], invoice.invoice_number)
        self.assertEqual(payload['InvoiceDate'], invoice.issue_date.isoformat())
        self.assertEqual(payload['RelatedPartyID'], 'B44531218')
        self.assertEqual(payload['RelatedPartyName'], 'Test client')
        self.assertEqual(invoice.client.tax_id, 'B87654321')

    def test_production_blocks_submission_and_test_download_before_any_io(self) -> None:
        app = FastAPI()
        app.include_router(router)
        invoice = sample_invoice('issued')
        with patch.dict(os.environ, {'ENV': 'production'}), TestClient(app) as client, \
             patch('issued.router.repository.read_invoice') as read, patch('issued.verifactu.httpx.post') as post:
            self.assertEqual(client.post(f'/api/billing/invoices/{invoice.id}/verifactu-test').status_code, 403)
            self.assertEqual(client.get(f'/api/billing/invoices/{invoice.id}/verifactu-test/pdf').status_code, 403)
            self.assertFalse(client.get('/api/billing/settings').json()['verifactu_test_enabled'])
            with self.assertRaises(HTTPException):
                submit_test(invoice)
        read.assert_not_called()
        post.assert_not_called()

    def test_failed_test_pdf_reuses_saved_receipt_without_resubmission(self) -> None:
        invoice = sample_invoice('issued')
        receipts: list[VerifactuTestReceipt] = []

        def save(value: IssuedInvoice, receipt: VerifactuTestReceipt) -> IssuedInvoice:
            invoice.verifactu_test = receipt.model_copy(deep=True)
            receipts.append(receipt.model_copy(deep=True))
            return invoice

        with patch.dict(os.environ, {'ENV': 'test'}), patch('issued.router.get_redis'), \
             patch('issued.router.repository.read_invoice', return_value=invoice), \
             patch('issued.router.submit_test', return_value=accepted_receipt()) as submit, \
             patch('issued.router.repository.save_verifactu_test', side_effect=save), \
             patch('issued.router.render_invoice', return_value=b'%PDF-test'), \
             patch('issued.router.upload_file', side_effect=[ConnectionError('storage'), None]) as upload:
            with self.assertRaises(ConnectionError):
                verifactu_test(invoice.id)
            self.assertIsNone(receipts[0].pdf_path)
            value = verifactu_test(invoice.id)
            verifactu_test(invoice.id)
        submit.assert_called_once()
        self.assertEqual(upload.call_count, 2)
        self.assertEqual(value.verifactu_test.pdf_path, f'issued/{invoice.id}/invoice.pdf')
        self.assertEqual(invoice.pdf_path, 'issued/example/invoice.pdf')

    def test_provider_rejection_does_not_get_a_success_receipt(self) -> None:
        response = MagicMock()
        response.json.return_value = {'Return': {'ErrorCode': 100, 'ErrorDescription': 'rejected'}}
        with patch.dict(os.environ, {'ENV': 'development', 'VERIFACTU_SERVICE_KEY': 'test-key'}), patch('issued.verifactu.httpx.post', return_value=response):
            with self.assertRaises(HTTPException) as error:
                submit_test(sample_invoice('issued'))
        self.assertEqual(error.exception.status_code, 422)

    def test_issuance_submits_before_publishing_and_retry_reuses_accepted_receipt(self) -> None:
        invoice = sample_invoice()
        events: list[str] = []

        def save(value: IssuedInvoice, receipt: VerifactuTestReceipt) -> IssuedInvoice:
            invoice.verifactu_test = receipt.model_copy(deep=True)
            events.append('receipt')
            return invoice

        def finish(value: IssuedInvoice, path: str) -> IssuedInvoice:
            invoice.status = 'issued'
            invoice.pdf_path = path
            events.append('issued')
            return invoice

        with patch.dict(os.environ, {'ENV': 'test'}), patch('issued.router.get_redis'), \
             patch('issued.router.repository.reserve_invoice', return_value=invoice), \
             patch('issued.router.submit_test', return_value=accepted_receipt()) as submit, \
             patch('issued.router.repository.save_verifactu_test', side_effect=save), \
             patch('issued.router.render_invoice', return_value=b'%PDF-test') as render, \
             patch('issued.router.upload_file', side_effect=lambda *args: events.append('pdf')) as upload, \
             patch('issued.router.repository.finish_invoice', side_effect=finish):
            issue(invoice.id, InvoiceInput.model_validate(invoice.model_dump()))
            invoice.status = 'paid'
            result = issue(invoice.id, InvoiceInput.model_validate(invoice.model_dump()))
        self.assertEqual(events, ['receipt', 'pdf', 'receipt', 'issued'])
        self.assertEqual(result.status, 'paid')
        self.assertEqual(result.verifactu_test.csv, 'TEST-CSV')
        self.assertIsNotNone(result.verifactu_test.submitted_at)
        submit.assert_called_once()
        upload.assert_called_once()
        render.assert_called_once_with(invoice, test_qr_code='data:image/bmp;base64,bitmap')

    def test_rejected_registration_keeps_generated_qr_without_success_receipt(self) -> None:
        invoice = sample_invoice('issued')
        invoice.verifactu_test = VerifactuTestReceipt(qr_code='generated-qr', csv=None, submitted_at=None, pdf_path=invoice.pdf_path)
        with patch.dict(os.environ, {'ENV': 'test'}), patch('issued.router.get_redis'), \
             patch('issued.router.repository.read_invoice', return_value=invoice), \
             patch('issued.router.submit_test', side_effect=HTTPException(422, 'verifactu_test_rejected')) as submit, \
             patch('issued.router.repository.save_verifactu_test') as save:
            with self.assertRaises(HTTPException):
                verifactu_test(invoice.id)
        submit.assert_called_once()
        save.assert_not_called()
        self.assertEqual(invoice.verifactu_test.qr_code, 'generated-qr')
        self.assertIsNone(invoice.verifactu_test.csv)

    def test_issuance_rejection_never_publishes_pdf_or_issued_status(self) -> None:
        invoice = sample_invoice()
        with patch.dict(os.environ, {'ENV': 'test'}), patch('issued.router.get_redis'), \
             patch('issued.router.repository.reserve_invoice', return_value=invoice), \
             patch('issued.router.submit_test', side_effect=HTTPException(422, 'verifactu_test_rejected')), \
             patch('issued.router.repository.save_verifactu_test') as save, \
             patch('issued.router.render_invoice') as render, \
             patch('issued.router.upload_file') as upload, \
             patch('issued.router.repository.finish_invoice') as finish:
            with self.assertRaises(HTTPException):
                issue(invoice.id, InvoiceInput.model_validate(invoice.model_dump()))
        save.assert_not_called()
        render.assert_not_called()
        upload.assert_not_called()
        finish.assert_not_called()

    def test_unregistered_qr_cannot_be_downloaded_as_a_verifactu_invoice(self) -> None:
        app = FastAPI()
        app.include_router(router)
        invoice = sample_invoice('issued')
        invoice.verifactu_test = VerifactuTestReceipt(qr_code='generated-qr', csv=None, submitted_at=None, pdf_path=invoice.pdf_path)
        with patch.dict(os.environ, {'ENV': 'test'}), TestClient(app) as client, \
             patch('issued.router.repository.read_invoice', return_value=invoice), patch('issued.router.download_file') as download:
            for suffix in ('pdf', 'verifactu-test/pdf'):
                response = client.get(f'/api/billing/invoices/{invoice.id}/{suffix}')
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()['detail'], 'verifactu_test_pending')
        download.assert_not_called()

    def test_qr_and_csv_without_acceptance_do_not_count_as_success(self) -> None:
        response = MagicMock()
        response.json.return_value = {'Return': {'StatusResponse': 'Incorrecto', 'QrCode': 'bitmap', 'CSV': 'TEST-CSV'}}
        with patch.dict(os.environ, {'ENV': 'test', 'VERIFACTU_SERVICE_KEY': 'test-key'}), patch('issued.verifactu.httpx.post', return_value=response):
            with self.assertRaises(HTTPException):
                submit_test(sample_invoice())
