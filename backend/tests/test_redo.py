import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from documents.repository import Document, reset_document
from documents.router import redo_document, router
from documents.queue import PROCESSING, QUEUE, RETRIES, SCHEDULED
from pipeline.extraction_3.extraction import InvoiceExtraction
from pipeline.runner import run_pipeline
from tests.test_stage_duration import queued_document


class RedoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = queued_document()
        self.document.status = "ready"
        self.events = MagicMock()
        self.redis = self.enterContext(patch("documents.router.get_redis")).return_value.__enter__.return_value
        self.redis.lpos.return_value = None
        self.read = self.enterContext(patch("documents.router.read_document", return_value=self.document))
        self.enterContext(patch("documents.router.reset_document", self.events.reset))
        self.enterContext(patch("documents.router.enqueue", self.events.enqueue))
        self.write = self.enterContext(patch("documents.router.write_document"))

    def test_successful_and_failed_files_can_restart_and_clear_the_ocr_checkpoint(self) -> None:
        for status in ("ready", "error"):
            with self.subTest(status=status):
                self.document.status = status
                self.events.reset_mock()
                redo_document(self.document.id)
                self.assertEqual([call[0] for call in self.events.mock_calls], ["reset", "enqueue"])
                self.events.reset.assert_called_once_with(self.document.id, self.document.name)
                self.events.enqueue.assert_called_once_with(str(self.document.id), self.document.name)
                transaction = self.redis.pipeline.return_value.__enter__.return_value
                transaction.delete.assert_called_with(f"documents:ocr:{self.document.id}")
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
                    redo_document(self.document.id)
                self.assertEqual(error.exception.status_code, 409)
        self.events.reset.assert_not_called()
        self.events.enqueue.assert_not_called()
        self.redis.pipeline.assert_not_called()

    def test_repeat_request_is_rejected_after_the_document_is_queued(self) -> None:
        def enqueue(identifier: str, name: str) -> None:
            self.document.status = "queued"

        self.events.enqueue.side_effect = enqueue
        redo_document(self.document.id)
        with self.assertRaises(HTTPException) as error:
            redo_document(self.document.id)
        self.assertEqual(error.exception.status_code, 409)
        self.events.enqueue.assert_called_once()

    def test_reset_failure_does_not_enqueue_and_leaves_file_retryable(self) -> None:
        self.events.reset.side_effect = ConnectionError("database")
        with self.assertRaises(HTTPException) as error:
            redo_document(self.document.id)
        self.assertEqual(error.exception.status_code, 503)
        self.events.enqueue.assert_not_called()
        self.write.assert_called_once_with(self.document)
        self.assertEqual(self.document.status, "error")

    def test_queue_failure_leaves_file_retryable(self) -> None:
        self.events.enqueue.side_effect = ConnectionError("queue")
        with self.assertRaises(HTTPException) as error:
            redo_document(self.document.id)
        self.assertEqual(error.exception.status_code, 503)
        self.write.assert_called_once_with(self.document)
        self.assertEqual(self.document.status, "error")

    def test_http_action_returns_accepted_without_changing_document_identity(self) -> None:
        queued = Document.model_validate({**self.document.model_dump(), "status": "queued", "pages": 0})
        self.read.side_effect = [self.document, queued]
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.post(f"/api/documents/{self.document.id}/redo")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["id"], str(self.document.id))
        self.assertEqual(response.json()["status"], "queued")
        self.redis.lpos.assert_called_once_with(PROCESSING, str(self.document.id))

    def test_reset_invalidates_all_results_and_erp_match_but_preserves_sources_and_usage(self) -> None:
        database = MagicMock()
        with patch("documents.repository.get_client", return_value=database):
            reset_document(self.document.id, self.document.name)
        self.assertEqual([call.args[0] for call in database.table.call_args_list], ["document_stages", "documents"])
        stage_update, document_update = database.table.return_value.update.call_args_list
        self.assertEqual(stage_update.args[0], {
            "status": "unavailable", "started_at": None, "finished_at": None,
            "duration_ms": None, "result_path": None,
        })
        fields = document_update.args[0]
        self.assertEqual(set(fields), (set(InvoiceExtraction.model_fields) - {"notes", "uncertainties"}) | {"status", "pages", "erp_entry_id"})
        self.assertEqual(fields["status"], "queued")
        self.assertTrue(all(value is None for key, value in fields.items() if key not in {"status", "pages"}))

    def test_reset_stages_run_every_phase_again(self) -> None:
        document = queued_document()
        for stage in document.stages:
            stage.status = "unavailable"
        events = MagicMock()
        with (
            patch("pipeline.runner.bind_snapshot"),
            patch("pipeline.runner.download_file", return_value=b"original PDF"),
            patch("pipeline.runner.process_text", events.text),
            patch("pipeline.runner.process_ocr", events.ocr),
            patch("pipeline.runner.process_extraction", events.extraction),
        ):
            run_pipeline(document)
        self.assertEqual([call[0] for call in events.mock_calls], ["text", "ocr", "extraction"])
