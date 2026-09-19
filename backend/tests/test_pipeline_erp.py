import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pipeline.erp import bind_snapshot, match_entry
from pipeline.runner import run_pipeline
from tests.test_stage_duration import queued_document


class PipelineErpTests(unittest.TestCase):
    def test_existing_document_snapshot_is_reused_without_reading_or_downloading(self) -> None:
        document = queued_document()
        document.erp_snapshot_id = uuid4()
        with patch("pipeline.erp.get_client") as database, patch("pipeline.erp.sync_erp_snapshot") as sync:
            bind_snapshot(document)
        database.assert_not_called()
        sync.assert_not_called()

    def test_latest_saved_snapshot_is_bound_without_downloading(self) -> None:
        document = queued_document()
        snapshot_id = uuid4()
        database = MagicMock()
        with (
            patch("pipeline.erp.latest_snapshot_id", return_value=snapshot_id),
            patch("pipeline.erp.get_client", return_value=database),
            patch("pipeline.erp.sync_erp_snapshot") as sync,
        ):
            bind_snapshot(document)
        self.assertEqual(document.erp_snapshot_id, snapshot_id)
        database.table.assert_called_once_with("documents")
        database.table.return_value.update.assert_called_once_with({"erp_snapshot_id": str(snapshot_id)})
        database.table.return_value.update.return_value.eq.assert_called_once_with("id", str(document.id))
        sync.assert_not_called()

    def test_first_snapshot_uses_upstream_sync_service(self) -> None:
        document = queued_document()
        snapshot_id = uuid4()
        with (
            patch("pipeline.erp.latest_snapshot_id", return_value=None),
            patch("pipeline.erp.get_client"),
            patch("pipeline.erp.get_redis"),
            patch("pipeline.erp.sync_erp_snapshot", return_value=snapshot_id) as sync,
        ):
            bind_snapshot(document)
        sync.assert_called_once_with()
        self.assertEqual(document.erp_snapshot_id, snapshot_id)

    def test_snapshot_created_by_another_worker_is_reused(self) -> None:
        document = queued_document()
        snapshot_id = uuid4()
        with (
            patch("pipeline.erp.latest_snapshot_id", side_effect=[None, snapshot_id]),
            patch("pipeline.erp.get_client"),
            patch("pipeline.erp.get_redis"),
            patch("pipeline.erp.sync_erp_snapshot") as sync,
        ):
            bind_snapshot(document)
        sync.assert_not_called()
        self.assertEqual(document.erp_snapshot_id, snapshot_id)

    def test_failed_snapshot_download_does_not_bind_document(self) -> None:
        document = queued_document()
        with (
            patch("pipeline.erp.latest_snapshot_id", return_value=None),
            patch("pipeline.erp.get_client") as database,
            patch("pipeline.erp.get_redis"),
            patch("pipeline.erp.sync_erp_snapshot", side_effect=ConnectionError("ERP unavailable")),
        ):
            with self.assertRaises(ConnectionError):
                bind_snapshot(document)
        database.assert_not_called()
        self.assertIsNone(document.erp_snapshot_id)

    def test_only_unique_matches_from_the_bound_snapshot_are_linked(self) -> None:
        document = queued_document()
        document.erp_snapshot_id = uuid4()
        entry_id = str(uuid4())
        for entries, expected in [([], None), ([{"id": entry_id}], entry_id), ([{"id": entry_id}, {"id": str(uuid4())}], None)]:
            with self.subTest(entries=entries), patch("pipeline.erp.get_client") as client:
                database = client.return_value
                query = database.table.return_value.select.return_value
                query.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = entries
                match_entry(document, "PO-123")
                query.eq.assert_called_once_with("snapshot_id", str(document.erp_snapshot_id))
                query.eq.return_value.eq.assert_called_once_with("order_id", "PO-123")
                query.eq.return_value.eq.return_value.limit.assert_called_once_with(2)
                database.table.return_value.update.assert_called_once_with({"erp_entry_id": expected})

    def test_missing_purchase_order_does_not_match_blank_erp_orders(self) -> None:
        document = queued_document()
        document.erp_snapshot_id = uuid4()
        with patch("pipeline.erp.get_client") as client:
            match_entry(document, "")
        client.return_value.table.assert_called_once_with("documents")
        client.return_value.table.return_value.update.assert_called_once_with({"erp_entry_id": None})

    def test_snapshot_is_bound_before_any_pipeline_phase(self) -> None:
        document = queued_document()
        events = MagicMock()
        with (
            patch("pipeline.runner.bind_snapshot", events.bind),
            patch("pipeline.runner.download_file", return_value=b"PDF"),
            patch("pipeline.runner.process_text", events.text),
            patch("pipeline.runner.process_ocr", events.ocr),
            patch("pipeline.runner.process_merge", events.merge),
            patch("pipeline.runner.process_extraction", events.extraction),
        ):
            run_pipeline(document)
        self.assertEqual([call[0] for call in events.mock_calls], ["bind", "text", "ocr", "merge", "extraction"])
