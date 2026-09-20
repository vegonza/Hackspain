import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from invoices.repository import Invoice, InvoiceBilling, read_invoice, write_invoice
from invoices.router import router


class InvoiceDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(router)

    def test_pdf_download_preserves_content_and_filename(self) -> None:
        invoice = Invoice(id=uuid4(), name="Factura café.pdf", sha256="a" * 64, created_at=datetime.now(timezone.utc))
        with patch("invoices.downloads.read_invoice", return_value=invoice), patch("invoices.downloads.download_file", return_value=b"%PDF-example"), TestClient(self.app) as client:
            response = client.get(f"/api/invoices/{invoice.id}/download")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"%PDF-example")
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn("Factura%20caf%C3%A9.pdf", response.headers["content-disposition"])

    def test_billing_fields_are_read_but_never_overwritten_by_worker_metadata(self) -> None:
        billing = {field: None for field in InvoiceBilling.model_fields}
        billing.update({"supplier_name": "Papelería", "total_eur": "121.00", "tax_base_eur": "100.00", "invoice_date": "2026-06-12"})
        row = {"id": str(uuid4()), "name": "invoice.pdf", "sha256": "a" * 64,
               "created_at": datetime.now(timezone.utc).isoformat(), **billing}
        database, redis = MagicMock(), MagicMock()
        database.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [row]
        redis.__enter__.return_value.hget.return_value = None
        with patch("invoices.repository.get_client", return_value=database), patch("invoices.repository.get_redis", return_value=redis):
            invoice = read_invoice(row["id"])
            self.assertEqual(invoice.billing.supplier_name, "Papelería")
            self.assertEqual(invoice.model_dump(mode="json")["billing"]["total_eur"], "121.00")
            write_invoice(invoice)
        self.assertEqual(set(database.table.return_value.upsert.call_args.args[0]), {"id", "name", "sha256", "created_at", "status", "pages"})
