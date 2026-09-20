from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from invoices.repository import Invoice
from invoices.router import delete_invoice


class InvoiceDeleteTests(TestCase):
    def setUp(self) -> None:
        self.invoice = Invoice(id=uuid4(), name="invoice.pdf", sha256="a" * 64,
                               created_at=datetime.now(timezone.utc), status="ready")
        self.enterContext(patch("invoices.router.read_invoice", return_value=self.invoice))
        self.remove = self.enterContext(patch("invoices.router.delete_file"))
        self.archive = self.enterContext(patch("invoices.router.archive_invoice"))
        self.enterContext(patch("invoices.router.invalidate_invoice_urls"))
        self.enterContext(patch("invoices.router.get_redis"))

    def test_deleting_invoice_removes_original_pdf(self) -> None:
        self.assertEqual(delete_invoice(self.invoice.id), {"deleted": True})
        self.remove.assert_called_once_with(f"{self.invoice.id}/original.pdf")
        self.archive.assert_called_once_with(self.invoice.id)

    def test_storage_failure_keeps_invoice_active_for_retry(self) -> None:
        self.remove.side_effect = RuntimeError("Storage unavailable")
        with self.assertRaises(RuntimeError):
            delete_invoice(self.invoice.id)
        self.archive.assert_not_called()

    def test_processing_invoice_keeps_original_pdf(self) -> None:
        for status in ("queued", "processing"):
            self.invoice.status = status
            with self.assertRaises(HTTPException) as raised:
                delete_invoice(self.invoice.id)
            self.assertEqual(raised.exception.status_code, 409)
        self.remove.assert_not_called()
        self.archive.assert_not_called()
