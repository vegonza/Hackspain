import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from invoices.repository import Invoice, reset_invoice
from invoices.router import redo_invoice, router
from invoices.queue import PROCESSING, QUEUE, RETRIES, SCHEDULED
from extractor.extraction import InvoiceExtraction
from tests.test_extraction_lifecycle import queued_invoice


class RedoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = queued_invoice()
        self.document.status = "ready"
        self.events = MagicMock()
        self.redis = self.enterContext(patch("invoices.router.get_redis")).return_value.__enter__.return_value
        self.redis.lpos.return_value = None
        self.read = self.enterContext(patch("invoices.router.read_invoice", return_value=self.document))
        self.enterContext(patch("invoices.router.reset_invoice", self.events.reset))
        self.enterContext(patch("invoices.router.enqueue", self.events.enqueue))
        self.write = self.enterContext(patch("invoices.router.write_invoice"))

    def test_successful_and_failed_files_can_restart_and_clear_retry_state(self) -> None:
        for status in ("ready", "error"):
            with self.subTest(status=status):
                self.document.status = status
                self.events.reset_mock()
                redo_invoice(self.document.id)
                self.assertEqual([call[0] for call in self.events.mock_calls], ["reset", "enqueue"])
                self.events.reset.assert_called_once_with(self.document.id, self.document.name)
                self.events.enqueue.assert_called_once_with(str(self.document.id), self.document.name)
                transaction = self.redis.pipeline.return_value.__enter__.return_value
                transaction.hdel.assert_called_with(RETRIES, str(self.document.id))
                transaction.zrem.assert_called_with(SCHEDULED, str(self.document.id))
                transaction.lrem.assert_called_with(QUEUE, 0, str(self.document.id))
                transaction.execute.assert_called()

    def test_queued_processing_and_not_yet_released_jobs_cannot_restart(self) -> None:
        for status, position in (("queued", None), ("processing", None), ("ready", 0), ("error", 1)):
            with self.subTest(status=status, position=position):
                self.document.status = status
                self.redis.lpos.return_value = position
                with self.assertRaises(HTTPException) as error:
                    redo_invoice(self.document.id)
                self.assertEqual(error.exception.status_code, 409)
        self.events.reset.assert_not_called()
        self.events.enqueue.assert_not_called()
        self.redis.pipeline.assert_not_called()

    def test_repeat_request_is_rejected_after_the_document_is_queued(self) -> None:
        def enqueue(identifier: str, name: str) -> None:
            self.document.status = "queued"

        self.events.enqueue.side_effect = enqueue
        redo_invoice(self.document.id)
        with self.assertRaises(HTTPException) as error:
            redo_invoice(self.document.id)
        self.assertEqual(error.exception.status_code, 409)
        self.events.enqueue.assert_called_once()

    def test_reset_failure_does_not_enqueue_and_leaves_file_retryable(self) -> None:
        self.events.reset.side_effect = ConnectionError("database")
        with self.assertRaises(HTTPException) as error:
            redo_invoice(self.document.id)
        self.assertEqual(error.exception.status_code, 503)
        self.events.enqueue.assert_not_called()
        self.write.assert_called_once_with(self.document)
        self.assertEqual(self.document.status, "error")

    def test_queue_failure_leaves_file_retryable(self) -> None:
        self.events.enqueue.side_effect = ConnectionError("queue")
        with self.assertRaises(HTTPException) as error:
            redo_invoice(self.document.id)
        self.assertEqual(error.exception.status_code, 503)
        self.write.assert_called_once_with(self.document)
        self.assertEqual(self.document.status, "error")

    def test_http_action_returns_accepted_without_changing_document_identity(self) -> None:
        queued = Invoice.model_validate({**self.document.model_dump(), "status": "queued", "pages": 0})
        self.read.side_effect = [self.document, queued]
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.post(f"/api/invoices/{self.document.id}/redo")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["id"], str(self.document.id))
        self.assertEqual(response.json()["status"], "queued")
        self.redis.lpos.assert_called_once_with(PROCESSING, str(self.document.id))

    def test_reset_invalidates_all_results_and_erp_match_but_preserves_sources_and_usage(self) -> None:
        database = MagicMock()
        with patch("invoices.repository.get_client", return_value=database):
            reset_invoice(self.document.id, self.document.name)
        database.table.assert_called_once_with("documents")
        fields = database.table.return_value.update.call_args.args[0]
        self.assertEqual(set(fields), (set(InvoiceExtraction.model_fields) - {"notes", "uncertainties"}) | {"status", "pages", "erp_entry_id", "payment_decision", "started_at", "finished_at", "duration_ms", "result_path"})
        self.assertEqual(fields["status"], "queued")
        self.assertTrue(all(value is None for key, value in fields.items() if key not in {"status", "pages"}))
