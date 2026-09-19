import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pipeline import ocr_2 as ocr_phase, text_1 as text_phase
from pipeline.runner import run_pipeline
from pipeline.results import invoice_stages
from invoices.repository import InvoiceDetails, write_invoice
from invoices.stages import StageDetail, stage_attempt
from invoices.worker import process_invoice
from shared.retries import RetryState

def queued_invoice() -> InvoiceDetails:
    identifier = uuid4()
    return InvoiceDetails(
        id=identifier, name="invoice.pdf", sha256="a" * 64,
        created_at=datetime.now(timezone.utc),
        stages=[StageDetail(invoice_id=identifier, stage=stage, status="unavailable" if stage == "extraction" else "queued") for stage in ("text", "ocr", "extraction")],
    )


class StageDurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(patch("pipeline.runner.bind_snapshot"))
        self.enterContext(patch("pipeline.runner.process_classification"))

    def test_stage_persistence_uses_existing_metadata_columns(self) -> None:
        invoice_record = queued_invoice()
        with patch("invoices.stages.get_client") as database:
            with stage_attempt(invoice_record.id, invoice_record.name, "text", "native.txt"):
                pass
        updates = database.return_value.table.return_value.update.call_args_list
        self.assertEqual([call.args[0]["status"] for call in updates], ["processing", "ready"])
        for call in updates:
            self.assertLessEqual(set(call.args[0]), {
                "status", "started_at", "finished_at", "duration_ms", "result_path",
            })

    def test_worker_only_completes_invoice_after_pipeline_returns(self) -> None:
        invoice_record = queued_invoice()
        saved: list[str] = []

        def capture(value: InvoiceDetails) -> None:
            saved.append(value.status)

        with (
            patch("invoices.worker.get_redis"),
            patch("invoices.worker.read_retry", return_value=RetryState()),
            patch("invoices.worker.read_invoice_detail", return_value=invoice_record),
            patch("invoices.worker.write_invoice", side_effect=capture),
            patch("invoices.worker.run_pipeline") as run,
        ):
            process_invoice(str(invoice_record.id))
        run.assert_called_once_with(invoice_record)
        self.assertEqual(saved, ["processing", "ready"])

    def test_ocr_checkpoint_saves_raw_response_images_and_markdown_without_another_call(self) -> None:
        response = {
            "model": "mistral-ocr-latest",
            "pages": [{
                "index": 0, "markdown": "![image](img)",
                "images": [{"id": "img", "top_left_x": 0, "top_left_y": 0,
                            "bottom_right_x": 10, "bottom_right_y": 10, "image_base64": "aGVsbG8="}],
                "dimensions": {"dpi": 200, "height": 100, "width": 100},
            }],
            "usage_info": {"pages_processed": 1, "doc_size_bytes": 20},
        }
        redis = MagicMock()
        redis.__enter__.return_value.get.return_value = json.dumps({"response": response, "usage": {"id": "usage-1"}})
        with (
            patch.dict("os.environ", {"MISTRAL_API_KEY": "test-key"}),
            patch.object(ocr_phase, "get_redis", return_value=redis),
            patch.object(ocr_phase, "request_ocr") as request,
            patch.object(ocr_phase, "upload_file") as upload,
        ):
            markdown, pages = ocr_phase.extract_markdown(b"PDF", "invoice-1", "invoice.pdf")
        self.assertEqual([call.args[0] for call in upload.call_args_list], [
            "invoice-1/ocr.json", "invoice-1/page-0-image-0.jpg", "invoice-1/document.md",
        ])
        self.assertEqual(json.loads(upload.call_args_list[0].args[1])["usage_info"]["pages_processed"], 1)
        self.assertEqual(upload.call_args_list[1].args[1], b"hello")
        self.assertEqual(upload.call_args_list[2].args[1], markdown.encode("utf-8"))
        self.assertIn("/api/documents/invoice-1/images/page-0-image-0.jpg", markdown)
        self.assertEqual(pages, 1)
        request.assert_not_called()

    def test_both_phases_save_artifacts_before_publishing_metrics(self) -> None:
        invoice_record = queued_invoice()
        events = MagicMock()
        with (
            patch("pipeline.runner.download_file", return_value=b"%PDF-test"),
            patch("pipeline.runner.process_extraction"),
            patch("invoices.stages.start_stage"),
            patch("invoices.stages.finish_stage", events.finish),
            patch("invoices.stages.fail_stage") as fail,
            patch("invoices.stages.time.perf_counter", side_effect=[10, 10.25, 20, 22.345]),
            patch.object(text_phase, "extract_text", return_value="Invoice text"),
            patch.object(text_phase, "upload_file", events.upload),
            patch.object(ocr_phase, "extract_markdown", return_value=("# Invoice", 2)),
            patch.object(ocr_phase, "write_invoice", events.invoice_record),
        ):
            run_pipeline(invoice_record)
        self.assertEqual(events.upload.call_args.args, (
            f"{invoice_record.id}/native.txt", b"Invoice text", "text/plain; charset=utf-8",
        ))
        self.assertEqual([call.args[2:] for call in events.finish.call_args_list], [
            ("text", 250, f"{invoice_record.id}/native.txt"),
            ("ocr", 2345, f"{invoice_record.id}/document.md"),
        ])
        self.assertEqual([call[0] for call in events.mock_calls], ["upload", "finish", "invoice_record", "finish"])
        self.assertEqual(invoice_record.pages, 2)
        fail.assert_not_called()

    def test_storage_failure_marks_text_failed_and_does_not_start_ocr(self) -> None:
        invoice_record = queued_invoice()
        with (
            patch("pipeline.runner.download_file", return_value=b"%PDF-test"),
            patch("pipeline.runner.process_ocr") as ocr,
            patch("pipeline.runner.process_extraction"),
            patch.object(text_phase, "extract_text", return_value="Invoice"),
            patch.object(text_phase, "upload_file", side_effect=ConnectionError("storage")),
            patch("invoices.stages.start_stage"),
            patch("invoices.stages.finish_stage") as finish,
            patch("invoices.stages.fail_stage") as fail,
            patch("invoices.stages.time.perf_counter", side_effect=[10, 10.5]),
        ):
            with self.assertRaises(ConnectionError):
                run_pipeline(invoice_record)
        fail.assert_called_once_with(invoice_record.id, invoice_record.name, "text", 500)
        finish.assert_not_called()
        ocr.assert_not_called()

    def test_retry_preserves_completed_text_and_resumes_ocr(self) -> None:
        invoice_record = queued_invoice()
        invoice_record.stages[0].status = "ready"
        invoice_record.stages[0].result_path = "native.txt"
        with (
            patch("pipeline.runner.download_file", return_value=b"PDF"),
            patch("pipeline.runner.process_text") as text,
            patch("pipeline.runner.process_ocr") as ocr,
            patch("pipeline.runner.process_extraction"),
        ):
            run_pipeline(invoice_record)
        text.assert_not_called()
        ocr.assert_called_once_with(b"PDF", invoice_record)

    def test_completed_pipeline_does_not_download_or_run_again(self) -> None:
        invoice_record = queued_invoice()
        for stage in invoice_record.stages:
            stage.status = "ready"
        with patch("pipeline.runner.download_file") as download:
            run_pipeline(invoice_record)
        download.assert_not_called()

    def test_empty_native_text_is_a_saved_zero_cost_result(self) -> None:
        invoice_record = queued_invoice()
        with (
            patch.object(text_phase, "extract_text", return_value=""),
            patch.object(text_phase, "upload_file") as upload,
            patch("invoices.stages.start_stage"),
            patch("invoices.stages.finish_stage") as finish,
        ):
            text_phase.process(b"PDF", invoice_record)
        self.assertEqual(upload.call_args.args[1], b"")
        self.assertEqual(finish.call_args.args[-1], f"{invoice_record.id}/native.txt")
        invoice_record.stages[0].status = "ready"
        invoice_record.stages[0].result_path = f"{invoice_record.id}/native.txt"
        with patch("pipeline.results.download_file", return_value=b""):
            stages = invoice_stages(invoice_record, invoice_record.stages)
        self.assertEqual(stages[1].cost_usd, Decimal(0))

    def test_metadata_failure_does_not_publish_a_successful_stage(self) -> None:
        invoice_record = queued_invoice()
        with (
            patch("invoices.stages.start_stage"),
            patch("invoices.stages.finish_stage", side_effect=ConnectionError("database")),
            patch("invoices.stages.fail_stage") as fail,
        ):
            with self.assertRaises(ConnectionError):
                with stage_attempt(invoice_record.id, invoice_record.name, "text", "native.txt"):
                    pass
        self.assertEqual(fail.call_args.args[2], "text")

    def test_historical_invoices_have_no_invented_duration(self) -> None:
        invoice_record = queued_invoice()
        invoice_record.status = "ready"
        for record in invoice_record.stages:
            record.status = "unavailable"
        stages = invoice_stages(invoice_record, invoice_record.stages)
        self.assertTrue(all(stage.duration_ms is None for stage in stages))
        self.assertEqual([stage.id for stage in stages], ["ocr", "text", "extraction"])

    def test_stage_result_and_cost_come_from_persistent_records(self) -> None:
        invoice_record = queued_invoice()
        invoice_record.stages[1] = StageDetail(
            invoice_id=invoice_record.id, stage="ocr", status="ready",
            result_path="ocr.md", duration_ms=1200, cost_usd=Decimal("0.008"),
        )
        with patch("pipeline.results.download_file", return_value=b"# OCR") as download:
            stages = invoice_stages(invoice_record, invoice_record.stages)
        self.assertEqual(stages[0].cost_usd, Decimal("0.008"))
        self.assertEqual(stages[0].content, "# OCR")
        self.assertEqual(stages[0].duration_ms, 1200)
        self.assertIsNone(stages[1].cost_usd)
        download.assert_called_once_with("ocr.md")

    def test_retry_status_targets_failed_phase_without_relabeling_completed_text(self) -> None:
        invoice_record = queued_invoice()
        invoice_record.next_retry_at = datetime.now(timezone.utc)
        invoice_record.stages[0].status = "ready"
        invoice_record.stages[0].result_path = "native.txt"
        invoice_record.stages[1].status = "error"
        with patch("pipeline.results.download_file", return_value=b"text"):
            stages = invoice_stages(invoice_record, invoice_record.stages)
        self.assertEqual([stage.status for stage in stages], ["retrying", "ready", "unavailable"])

    def test_saving_invoice_snapshot_does_not_write_stage_fields_to_invoices(self) -> None:
        invoice_record = queued_invoice()
        with patch("invoices.repository.get_client") as client:
            write_invoice(invoice_record)
        saved = client.return_value.table.return_value.upsert.call_args.args[0]
        self.assertEqual(set(saved), {"id", "name", "sha256", "created_at", "status", "pages"})
        self.assertNotIn("stages", saved)
        self.assertNotIn("retry_attempts", saved)
        self.assertEqual(saved["id"], str(invoice_record.id))
