import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from documents.repository import read_document_detail
from shared.retries import RetryState


class DocumentDetailTests(unittest.TestCase):
    def test_single_rpc_with_redis_retry_overlay(self) -> None:
        identifier = uuid4()
        client, redis = MagicMock(), MagicMock()
        client.rpc.return_value.execute.return_value.data = {
            "id": str(identifier), "name": "invoice.pdf", "sha256": "a" * 64,
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "processing",
            "stages": [{"document_id": str(identifier), "stage": "ocr", "status": "error", "cost_usd": "0.008"}],
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
