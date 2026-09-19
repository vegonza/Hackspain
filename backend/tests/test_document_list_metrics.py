import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from documents.repository import Document, StageMetrics, list_documents, write_document


class DocumentListMetricsTests(unittest.TestCase):
    def test_list_preserves_rpc_metrics_and_retry_state(self) -> None:
        identifier = uuid4()
        client, redis = MagicMock(), MagicMock()
        client.rpc.return_value.execute.return_value.data = [{
            "id": str(identifier), "name": "invoice.pdf", "sha256": "a" * 64,
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "processing",
            "total_cost_usd": "0.0047", "total_duration_ms": 9860,
            "current_stages": ["ocr", "extraction"],
            "stage_metrics": [{"stage": "extraction", "cost_usd": "0.004", "duration_ms": 8420}],
        }]
        redis.__enter__.return_value.hmget.return_value = [None]
        with patch("documents.repository.get_client", return_value=client), patch("documents.repository.get_redis", return_value=redis):
            result = list_documents()
        client.rpc.assert_called_once_with("get_documents", {"p_offset": 0, "p_limit": 1000})
        self.assertEqual(result[0].total_cost_usd, Decimal("0.0047"))
        self.assertEqual(result[0].current_stages, ["ocr", "extraction"])
        self.assertEqual(result[0].stage_metrics[0].stage, "extraction")
        self.assertEqual(result[0].stage_metrics[0].duration_ms, 8420)

    def test_aggregated_metrics_are_not_written_into_documents(self) -> None:
        document = Document(id=uuid4(), name="invoice.pdf", sha256="a" * 64,
                            created_at=datetime.now(timezone.utc), total_cost_usd=Decimal("0.004"),
                            stage_metrics=[StageMetrics(stage="ocr", duration_ms=10)])
        client = MagicMock()
        with patch("documents.repository.get_client", return_value=client):
            write_document(document)
        payload = client.table.return_value.upsert.call_args.args[0]
        self.assertEqual(set(payload), {"id", "name", "sha256", "created_at", "status", "pages"})
