import subprocess
from io import BytesIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from hashlib import sha256

from fastapi import HTTPException, UploadFile

from invoices.conversion import to_pdf
from invoices.router import upload_invoice


class InvoiceConversionTests(TestCase):
    def test_pdf_is_preserved_without_running_libreoffice(self) -> None:
        with patch('invoices.conversion.subprocess.run') as run:
            self.assertEqual(to_pdf(b'%PDF-original', 'invoice.PDF'), b'%PDF-original')
        run.assert_not_called()

    def test_conversion_uses_separate_profiles_and_cleans_temporary_files(self) -> None:
        profiles: list[str] = []
        sources: list[Path] = []

        def convert(command: list[str], **kwargs: object) -> None:
            profiles.append(command[1])
            source = Path(command[-1])
            sources.append(source)
            self.assertEqual(source.read_bytes(), b'office-content')
            source.with_suffix('.pdf').write_bytes(b'%PDF-converted')

        with patch('invoices.conversion.subprocess.run', side_effect=convert):
            for name in ('invoice.docx', 'slides.pptx', 'sheet.xlsx'):
                self.assertEqual(to_pdf(b'office-content', name), b'%PDF-converted')
        self.assertEqual(len(set(profiles)), 3)
        self.assertTrue(all(not source.parent.exists() for source in sources))

    def test_failed_or_missing_conversion_is_reported(self) -> None:
        for error in (subprocess.TimeoutExpired('libreoffice', 120), None):
            with self.subTest(error=error), patch('invoices.conversion.subprocess.run', side_effect=error):
                with self.assertRaises(HTTPException) as raised:
                    to_pdf(b'invalid', 'invoice.docx')
                self.assertEqual(raised.exception.detail, 'conversion_failed')

    def test_office_hashes_the_original_but_stores_pdf(self) -> None:
        original = b'office-content'
        with patch('invoices.router.find_invoice_by_hash', return_value=False), \
             patch('invoices.router.to_pdf', return_value=b'%PDF-converted') as convert, \
             patch('invoices.router.upload_file') as store, \
             patch('invoices.router.create_invoice'), patch('invoices.router.enqueue'):
            invoice = upload_invoice(UploadFile(filename='invoice.docx', file=BytesIO(original)))
        self.assertEqual(invoice.sha256, sha256(original).hexdigest())
        self.assertEqual(invoice.name, 'invoice.docx')
        convert.assert_called_once_with(original, 'invoice.docx')
        store.assert_called_once_with(f'{invoice.id}/original.pdf', b'%PDF-converted', 'application/pdf')

    def test_invalid_pdf_and_unsupported_files_are_rejected(self) -> None:
        for name, detail in (('invoice.pdf', 'invalid_pdf'), ('archive.zip', 'unsupported_file_type')):
            with self.subTest(name=name), self.assertRaises(HTTPException) as raised:
                to_pdf(b'invalid', name)
            self.assertEqual(raised.exception.detail, detail)
