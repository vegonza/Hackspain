import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from documents.repository import Document
from documents.pipeline import document_stages
from documents.stages import StageDetail
from documents.worker import process_document
from shared.retries import RetryState


class StageDurationTests(unittest.TestCase):
    def test_completed_ocr_persists_elapsed_time(self) -> None:
        document = Document(id=uuid4(), name="timing.pdf", sha256="a" * 64,
                            created_at=datetime.now(timezone.utc))
        redis = MagicMock()
        with (
            patch("documents.worker.get_redis", return_value=redis),
            patch("documents.worker.read_retry", return_value=RetryState()),
            patch("documents.worker.read_document", return_value=document),
            patch("documents.worker.write_document"),
            patch("documents.worker.start_stage"),
            patch("documents.worker.finish_stage") as finish,
            patch("documents.worker.fail_stage"),
            patch("documents.worker.download_file", return_value=b"%PDF-test"),
            patch("documents.worker.extract_markdown", return_value=("# Invoice", 1)),
            patch("documents.worker.upload_file"),
            patch("documents.worker.time.perf_counter", side_effect=[10, 12.345]),
        ):
            process_document(str(document.id))
        self.assertEqual(finish.call_args.args[3], 2345)
        self.assertEqual(finish.call_args.args[4], f"{document.id}/document.md")

    def test_historical_documents_have_no_invented_duration(self) -> None:
        document = Document(id=uuid4(), name="old.pdf", sha256="a" * 64,
                            created_at=datetime.now(timezone.utc), status="ready")
        records = [StageDetail(document_id=document.id, stage=stage, status="unavailable") for stage in ("ocr", "text", "merge")]
        self.assertTrue(all(stage.duration_ms is None for stage in document_stages(document, records)))

    def test_stage_result_and_cost_come_from_persistent_records(self) -> None:
        from decimal import Decimal
        document = Document(id=uuid4(), name="invoice.pdf", sha256="a" * 64,
                            created_at=datetime.now(timezone.utc), status="processing")
        records = [StageDetail(document_id=document.id, stage=stage, status="unavailable") for stage in ("ocr", "text", "merge")]
        records[0] = StageDetail(document_id=document.id, stage="ocr", status="ready", result_path="ocr.md", duration_ms=1200, cost_usd=Decimal("0.008"))
        with patch("documents.pipeline.download_file", return_value=b"# OCR") as download:
            stages = document_stages(document, records)
        self.assertEqual(stages[0].cost_usd, Decimal("0.008"))
        self.assertEqual(stages[0].content, "# OCR")
        self.assertEqual(stages[0].duration_ms, 1200)
        self.assertIsNone(stages[1].cost_usd)
        download.assert_called_once_with("ocr.md")
