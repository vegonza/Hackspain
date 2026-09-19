import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from invoices.repository import Invoice, list_invoices, write_invoice


class InvoiceListMetricsTests(unittest.TestCase):
    def test_list_preserves_rpc_metrics_and_retry_state(self) -> None:
        identifier = uuid4()
        client, redis = MagicMock(), MagicMock()
        client.rpc.return_value.execute.return_value.data = [{
            "id": str(identifier), "name": "invoice.pdf", "sha256": "a" * 64,
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "processing",
            "finished_at": "2026-09-19T10:00:03+00:00",
            "total_cost_usd": "0.0047", "total_duration_ms": 9860,
        }]
        redis.__enter__.return_value.hmget.return_value = [None]
        with patch("invoices.repository.get_client", return_value=client), patch("invoices.repository.get_redis", return_value=redis):
            result = list_invoices()
        client.rpc.assert_called_once_with("get_documents", {"p_offset": 0, "p_limit": 1000})
        self.assertEqual(result[0].total_cost_usd, Decimal("0.0047"))
        self.assertIsNone(result[0].finished_at)
        client.table.assert_not_called()

    def test_finished_time_uses_saved_completion_timestamp_instead_of_summed_durations(self) -> None:
        identifier = uuid4()
        client, redis = MagicMock(), MagicMock()
        client.rpc.return_value.execute.return_value.data = [{
            "id": str(identifier), "name": "invoice.pdf", "sha256": "a" * 64,
            "created_at": "2026-09-19T10:00:00+00:00", "status": "ready",
            "total_duration_ms": 7000,
            "finished_at": "2026-09-19T10:00:20+00:00",
        }]
        redis.__enter__.return_value.hmget.return_value = [None]
        with patch("invoices.repository.get_client", return_value=client), patch("invoices.repository.get_redis", return_value=redis):
            result = list_invoices()
        self.assertEqual(result[0].finished_at, datetime(2026, 9, 19, 10, 0, 20, tzinfo=timezone.utc))
        self.assertEqual((result[0].finished_at - result[0].created_at).total_seconds(), 20)
        client.table.assert_not_called()

    def test_completion_times_are_returned_with_each_document_page(self) -> None:
        client, redis = MagicMock(), MagicMock()
        rows = [{
            "id": str(uuid4()), "name": "invoice.pdf", "sha256": "a" * 64,
            "created_at": "2026-09-19T10:00:00+00:00", "status": "ready",
            "finished_at": "2026-09-19T10:00:20+00:00",
        } for _ in range(1001)]
        client.rpc.return_value.execute.side_effect = [
            MagicMock(data=rows[:1000]), MagicMock(data=rows[1000:]),
        ]
        redis.__enter__.return_value.hmget.side_effect = [[None] * 1000, [None]]
        with patch("invoices.repository.get_client", return_value=client), patch("invoices.repository.get_redis", return_value=redis):
            result = list_invoices()
        self.assertEqual(len(result), 1001)
        self.assertTrue(all(document.finished_at == datetime(2026, 9, 19, 10, 0, 20, tzinfo=timezone.utc) for document in result))
        self.assertEqual([call.args for call in client.rpc.call_args_list], [
            ("get_documents", {"p_offset": 0, "p_limit": 1000}),
            ("get_documents", {"p_offset": 1000, "p_limit": 1000}),
        ])
        client.table.assert_not_called()

    def test_retry_status_controls_whether_completion_time_is_exposed(self) -> None:
        for state, expected_status, finished in [
            ('{"failed":true}', "error", True),
            ('{"next_attempt":1800353000}', "queued", False),
        ]:
            with self.subTest(state=state):
                client, redis = MagicMock(), MagicMock()
                client.rpc.return_value.execute.return_value.data = [{
                    "id": str(uuid4()), "name": "invoice.pdf", "sha256": "a" * 64,
                    "created_at": "2026-09-19T10:00:00+00:00", "status": "processing",
                    "finished_at": "2026-09-19T10:00:20+00:00",
                }]
                redis.__enter__.return_value.hmget.return_value = [state]
                with patch("invoices.repository.get_client", return_value=client), patch("invoices.repository.get_redis", return_value=redis):
                    result = list_invoices()
                self.assertEqual(result[0].status, expected_status)
                self.assertEqual(result[0].finished_at is not None, finished)
                client.table.assert_not_called()

    def test_aggregated_metrics_are_not_written_into_documents(self) -> None:
        document = Invoice(id=uuid4(), name="invoice.pdf", sha256="a" * 64,
                            created_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc), total_cost_usd=Decimal("0.004"),
                            total_duration_ms=10)
        client = MagicMock()
        with patch("invoices.repository.get_client", return_value=client):
            write_invoice(document)
        payload = client.table.return_value.upsert.call_args.args[0]
        self.assertEqual(set(payload), {"id", "name", "sha256", "created_at", "status", "pages"})
