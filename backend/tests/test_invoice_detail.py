import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from pipeline.extraction_3.extraction import InvoiceExtraction
from invoices.repository import read_invoice_detail, save_invoice_extraction
from invoices.router import router
from shared.retries import RetryState


class InvoiceDetailTests(unittest.TestCase):
    def test_open_invoice_preserves_all_existing_database_stages(self) -> None:
        identifier = uuid4()
        database, redis = MagicMock(), MagicMock()
        database.rpc.return_value.execute.return_value.data = {
            "id": str(identifier), "name": "invoice.pdf", "sha256": "a" * 64,
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "ready",
            "erp_snapshot_id": str(uuid4()),
            "erp": {"entry_id": "AS-REAL", "supplier_id": "P-REAL", "tax_id": "B12345678",
                    "order_id": "PO-1", "status": "PAGADA", "raw_date": "12/01/2026",
                    "raw_amount": "12,10", "date": "2026-01-12", "amount": "12.10", "warnings": []},
            "stages": [
                {"document_id": str(identifier), "stage": "ocr", "status": "ready",
                 "result_path": "document.md", "duration_ms": 1200, "cost_usd": "0.004"},
                {"document_id": str(identifier), "stage": "text", "status": "ready", "result_path": "native.txt"},
                {"document_id": str(identifier), "stage": "extraction", "status": "ready",
                 "result_path": "extraction/features.json", "duration_ms": 2400, "cost_usd": "0.002",
                 "finished_at": "2026-09-19T10:00:20+00:00"},
            ],
        }
        redis.__enter__.return_value.hget.return_value = None
        extraction = InvoiceExtraction(
            invoice_number="INV-1", supplier_name="Proveedor", supplier_nif="N-1", iban="Account",
            invoice_date="2026-01-01", purchase_order="PO-1", line_items=[],
            tax_base="10", vat_rate="21", vat_amount="2.10", total="12.10", notes=[], uncertainties=[],
        )
        artifacts = {"document.md": b"# Invoice", "native.txt": b"Invoice",
                     "extraction/features.json": extraction.model_dump_json().encode("utf-8")}
        app = FastAPI()
        app.include_router(router)
        with (
            patch("invoices.repository.get_client", return_value=database),
            patch("invoices.repository.get_redis", return_value=redis),
            patch("pipeline.results.download_file", side_effect=artifacts.__getitem__),
            patch("pipeline.extraction_3.extraction.create_extractor") as extract,
            TestClient(app) as client,
        ):
            response = client.get(f"/api/invoices/{identifier}")
            repeated = client.get(f"/api/invoices/{identifier}")
            self.assertEqual(response.json(), repeated.json())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["finished_at"], "2026-09-19T10:00:20Z")
        self.assertEqual(response.json()["erp"]["status"], "PAGADA")
        self.assertEqual(response.json()["erp"]["entry_id"], "AS-REAL")
        database.table.assert_not_called()
        stages = response.json()["stages"]
        self.assertEqual([stage["id"] for stage in stages], ["ocr", "text", "extraction"])
        self.assertEqual(stages[0]["cost_usd"], "0.004")
        self.assertEqual(stages[2]["status"], "ready")
        self.assertEqual(stages[2]["depends_on"], ["ocr", "text"])
        self.assertEqual(stages[2]["cost_usd"], "0.002")
        self.assertEqual(response.json()["extraction"], extraction.model_dump())
        extract.assert_not_called()

    def test_single_rpc_with_redis_retry_overlay(self) -> None:
        identifier = uuid4()
        client, redis = MagicMock(), MagicMock()
        client.rpc.return_value.execute.return_value.data = {
            "id": str(identifier), "name": "invoice.pdf", "sha256": "a" * 64,
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "processing",
            "line_items": None,
            "stages": [{"document_id": str(identifier), "stage": "extraction", "status": "error", "cost_usd": "0.008"}],
        }
        redis.__enter__.return_value.hget.return_value = RetryState(attempts=2, next_attempt=2000000000).model_dump_json()
        with patch("invoices.repository.get_client", return_value=client), patch("invoices.repository.get_redis", return_value=redis):
            detail = read_invoice_detail(identifier)
        client.rpc.assert_called_once_with("get_document_detail", {"p_document_id": str(identifier)})
        client.table.assert_not_called()
        self.assertEqual(detail.status, "queued")
        self.assertEqual(detail.retry_attempts, 2)
        self.assertEqual(str(detail.stages[0].cost_usd), "0.008")

    def test_missing_or_archived_invoice_returns_404_without_redis(self) -> None:
        client = MagicMock()
        client.rpc.return_value.execute.return_value.data = None
        with patch("invoices.repository.get_client", return_value=client), patch("invoices.repository.get_redis") as redis:
            with self.assertRaises(HTTPException) as error:
                read_invoice_detail(uuid4())
        self.assertEqual(error.exception.status_code, 404)
        redis.assert_not_called()

    def test_result_preserves_raw_date_and_decimal_precision(self) -> None:
        extraction = InvoiceExtraction(
            invoice_number="F-1", supplier_name="Proveedor", supplier_nif="B12345678",
            iban="ES123", invoice_date="31/02/2026", purchase_order="PO-1",
            line_items=[], tax_base="123456789012345.12", vat_rate="21",
            vat_amount="25925925692592.4752", total="149382714704937.5952",
            notes=["Nota impresa"], uncertainties=["Fecha imposible"],
        )
        identifier = uuid4()
        client = MagicMock()
        with patch("invoices.repository.get_client", return_value=client):
            save_invoice_extraction(identifier, "invoice.pdf", extraction)
        payload = client.table.return_value.update.call_args.args[0]
        self.assertEqual(payload["invoice_date"], "31/02/2026")
        self.assertEqual(payload["total"], "149382714704937.5952")
        self.assertEqual(set(payload), (set(InvoiceExtraction.model_fields) - {"notes", "uncertainties"}) | {"payment_decision"})
        client.table.return_value.update.return_value.eq.assert_called_once_with("id", str(identifier))
        self.assertEqual(InvoiceExtraction.model_validate_json(extraction.model_dump_json()), extraction)

    def test_missing_amounts_are_stored_as_null_without_changing_the_artifact_fields(self) -> None:
        extraction = InvoiceExtraction(
            invoice_number="F-1", supplier_name="Proveedor", supplier_nif="B12345678",
            iban="", invoice_date="", purchase_order="", line_items=[],
            tax_base="", vat_rate="", vat_amount="", total="", notes=[], uncertainties=["Importes ilegibles"],
        )
        with patch("invoices.repository.get_client") as client:
            save_invoice_extraction(uuid4(), "invoice.pdf", extraction)
        payload = client.return_value.table.return_value.update.call_args.args[0]
        for field in ("tax_base", "vat_rate", "vat_amount", "total"):
            self.assertIsNone(payload[field])
            self.assertEqual(getattr(extraction, field), "")
