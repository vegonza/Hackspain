import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from documents.repository import read_document_detail, save_document_features
from documents.features import InvoiceFeatures
from shared.retries import RetryState


class DocumentDetailTests(unittest.TestCase):
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
        with patch("documents.repository.get_client", return_value=client), patch("documents.repository.get_redis", return_value=redis):
            detail = read_document_detail(identifier)
        client.rpc.assert_called_once_with("get_document_detail", {"p_document_id": str(identifier)})
        client.table.assert_not_called()
        self.assertEqual(detail.status, "queued")
        self.assertEqual(detail.retry_attempts, 2)
        self.assertEqual(str(detail.stages[0].cost_usd), "0.008")

    def test_missing_or_archived_document_returns_404_without_redis(self) -> None:
        client = MagicMock()
        client.rpc.return_value.execute.return_value.data = None
        with patch("documents.repository.get_client", return_value=client), patch("documents.repository.get_redis") as redis:
            with self.assertRaises(HTTPException) as error:
                read_document_detail(uuid4())
        self.assertEqual(error.exception.status_code, 404)
        redis.assert_not_called()

    def test_result_preserves_raw_date_and_decimal_precision(self) -> None:
        features = InvoiceFeatures(
            invoice_number="F-1", supplier_name="Proveedor", supplier_nif="B12345678",
            iban="ES123", invoice_date="31/02/2026", purchase_order="PO-1",
            line_items=[], tax_base="123456789012345.12", vat_rate="21",
            vat_amount="25925925692592.4752", total="149382714704937.5952",
        )
        identifier = uuid4()
        client, redis = MagicMock(), MagicMock()
        with patch("documents.repository.get_client", return_value=client):
            save_document_features(identifier, "invoice.pdf", features)
        payload = client.table.return_value.update.call_args.args[0]
        self.assertEqual(payload["invoice_date"], "31/02/2026")
        self.assertEqual(payload["total"], "149382714704937.5952")
        self.assertNotIn("status", payload)
        client.table.return_value.update.return_value.eq.assert_called_once_with("id", str(identifier))
        client.rpc.return_value.execute.return_value.data = {
            "id": str(identifier), "name": "invoice.pdf", "sha256": "a" * 64,
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "ready",
            **payload, "stages": [],
        }
        redis.__enter__.return_value.hget.return_value = None
        with patch("documents.repository.get_client", return_value=client), patch("documents.repository.get_redis", return_value=redis):
            detail = read_document_detail(identifier)
        self.assertEqual(detail.features, features)
