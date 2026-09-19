from hashlib import sha256
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from postgrest.exceptions import APIError

from documents.router import upload_document


class DocumentHashTests(TestCase):
    def test_new_document_hashes_original_bytes(self) -> None:
        content = b'%PDF-1.7\nexample'
        with patch('documents.router.find_document_by_hash', return_value=False) as lookup, patch('documents.router.upload_file'), patch('documents.router.create_document') as create, patch('documents.router.enqueue') as enqueue:
            document = upload_document(UploadFile(filename='test.pdf', file=BytesIO(content)))
        self.assertEqual(document.sha256, sha256(content).hexdigest())
        lookup.assert_called_once_with(document.sha256)
        create.assert_called_once_with(document)
        enqueue.assert_called_once_with(str(document.id), 'test.pdf')

    def test_identical_pdf_with_another_name_does_not_upload_or_enqueue(self) -> None:
        with patch('documents.router.find_document_by_hash', return_value=True), patch('documents.router.upload_file') as storage, patch('documents.router.create_document') as create, patch('documents.router.enqueue') as enqueue:
            with self.assertRaises(HTTPException) as raised:
                upload_document(UploadFile(filename='renamed.pdf', file=BytesIO(b'%PDF-1.7\nexample')))
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, 'duplicate_pdf')
        storage.assert_not_called()
        create.assert_not_called()
        enqueue.assert_not_called()

    def test_concurrent_unique_conflict_cleans_up_its_own_file(self) -> None:
        error = APIError({'code': '23505', 'message': 'unique violation', 'details': '', 'hint': ''})
        with patch('documents.router.find_document_by_hash', return_value=False), patch('documents.router.upload_file') as storage, patch('documents.router.create_document', side_effect=error), patch('documents.router.delete_file') as cleanup, patch('documents.router.enqueue') as enqueue:
            with self.assertRaises(HTTPException) as raised:
                upload_document(UploadFile(filename='test.pdf', file=BytesIO(b'%PDF-1.7\nexample')))
        self.assertEqual(raised.exception.status_code, 409)
        cleanup.assert_called_once_with(storage.call_args.args[0])
        enqueue.assert_not_called()

    def test_same_name_different_contents_have_different_hashes(self) -> None:
        with patch('documents.router.find_document_by_hash', return_value=False), patch('documents.router.upload_file'), patch('documents.router.create_document'), patch('documents.router.enqueue'):
            first = upload_document(UploadFile(filename='test.pdf', file=BytesIO(b'%PDF-first')))
            second = upload_document(UploadFile(filename='test.pdf', file=BytesIO(b'%PDF-second')))
        self.assertNotEqual(first.sha256, second.sha256)
