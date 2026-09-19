from hashlib import sha256
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from postgrest.exceptions import APIError

from invoices.router import upload_invoice


class InvoiceHashTests(TestCase):
    def test_new_invoice_hashes_original_bytes(self) -> None:
        content = b'%PDF-1.7\nexample'
        with patch('invoices.router.find_invoice_by_hash', return_value=False) as lookup, patch('invoices.router.upload_file'), patch('invoices.router.create_invoice') as create, patch('invoices.router.enqueue') as enqueue:
            invoice_record = upload_invoice(UploadFile(filename='test.pdf', file=BytesIO(content)))
        self.assertEqual(invoice_record.sha256, sha256(content).hexdigest())
        lookup.assert_called_once_with(invoice_record.sha256)
        create.assert_called_once_with(invoice_record)
        enqueue.assert_called_once_with(str(invoice_record.id), 'test.pdf')

    def test_identical_pdf_with_another_name_does_not_upload_or_enqueue(self) -> None:
        with patch('invoices.router.find_invoice_by_hash', return_value=True), patch('invoices.router.upload_file') as storage, patch('invoices.router.create_invoice') as create, patch('invoices.router.enqueue') as enqueue:
            with self.assertRaises(HTTPException) as raised:
                upload_invoice(UploadFile(filename='renamed.pdf', file=BytesIO(b'%PDF-1.7\nexample')))
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, 'duplicate_pdf')
        storage.assert_not_called()
        create.assert_not_called()
        enqueue.assert_not_called()

    def test_concurrent_unique_conflict_cleans_up_its_own_file(self) -> None:
        error = APIError({'code': '23505', 'message': 'unique violation', 'details': '', 'hint': ''})
        with patch('invoices.router.find_invoice_by_hash', return_value=False), patch('invoices.router.upload_file') as storage, patch('invoices.router.create_invoice', side_effect=error), patch('invoices.router.delete_file') as cleanup, patch('invoices.router.enqueue') as enqueue:
            with self.assertRaises(HTTPException) as raised:
                upload_invoice(UploadFile(filename='test.pdf', file=BytesIO(b'%PDF-1.7\nexample')))
        self.assertEqual(raised.exception.status_code, 409)
        cleanup.assert_called_once_with(storage.call_args.args[0])
        enqueue.assert_not_called()

    def test_same_name_different_contents_have_different_hashes(self) -> None:
        with patch('invoices.router.find_invoice_by_hash', return_value=False), patch('invoices.router.upload_file'), patch('invoices.router.create_invoice'), patch('invoices.router.enqueue'):
            first = upload_invoice(UploadFile(filename='test.pdf', file=BytesIO(b'%PDF-first')))
            second = upload_invoice(UploadFile(filename='test.pdf', file=BytesIO(b'%PDF-second')))
        self.assertNotEqual(first.sha256, second.sha256)
