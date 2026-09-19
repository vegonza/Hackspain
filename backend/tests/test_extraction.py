import json
import unittest
from decimal import Decimal
from hashlib import sha256
from unittest.mock import MagicMock, patch

from openai.types.chat import ChatCompletion

from documents.router import document_detail
from pipeline.extraction_4.extraction import InvoiceExtraction, SourcedInvoiceLine
from pipeline.extraction_4.extractor import PROMPTS_DIRECTORY
from pipeline.extraction_4.processor import process
from pipeline.results import document_stages
from pipeline.runner import run_pipeline
from shared.usage import UsageRecord
from tests.test_features import extracted_items
from tests.test_stage_duration import queued_document


class ExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = queued_document()
        self.markdown = b"Servicio 31,50"
        self.corrections = json.dumps({"corrections": [], "unresolved": ["Firma ilegible", "Sello ilegible"]}).encode()
        self.result = extracted_items([SourcedInvoiceLine(description="Servicio", source_line=1, amount_token=1)])
        self.result.uncertainties = ["Firma ilegible"]
        self.result.notes = ["Pago a 30 días"]
        self.events = MagicMock()
        self.enterContext(patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}))
        self.download = self.enterContext(patch("pipeline.extraction_4.processor.download_file", side_effect=[
            self.markdown, self.corrections,
        ]))
        self.enterContext(patch("pipeline.extraction_4.processor.upload_file", self.events.upload))
        self.enterContext(patch("pipeline.extraction_4.processor.save_document_extraction", self.events.save_extraction))
        self.enterContext(patch("pipeline.extraction_4.processor.match_entry", self.events.match_entry))
        self.enterContext(patch("documents.stages.start_stage"))
        self.enterContext(patch("documents.stages.finish_stage", self.events.finish))
        self.enterContext(patch("documents.stages.fail_stage", self.events.fail))
        self.enterContext(patch("documents.stages.time.perf_counter", side_effect=[10, 11.5]))
        self.redis = self.enterContext(patch("shared.usage.get_redis")).return_value.__enter__.return_value
        self.client_factory = self.enterContext(patch("pipeline.extraction_4.extractor.OpenAI"))
        self.request = self.client_factory.return_value.__enter__.return_value.chat.completions.create

    def prepare_response(self) -> None:
        self.request.return_value = ChatCompletion.model_validate({
            "id": "response-1", "created": 0, "object": "chat.completion", "model": "google/gemini-3.5-flash-lite",
            "usage": {"cost": "0.002", "prompt_tokens": 300, "completion_tokens": 120, "total_tokens": 420},
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "SourcedInvoiceExtraction", "arguments": self.result.model_dump_json()},
            }]}}],
        })

    def test_openrouter_extraction_preserves_source_amounts_notes_and_merge_uncertainties(self) -> None:
        self.prepare_response()
        process(self.document)
        prefix = f"{self.document.id}/extraction"
        self.assertEqual([call.args[0] for call in self.download.call_args_list], [
            f"{self.document.id}/merge/document.md", f"{self.document.id}/merge/corrections.json",
        ])
        artifacts = {call.args[0]: call.args[1] for call in self.events.upload.call_args_list}
        extraction = InvoiceExtraction.model_validate_json(artifacts[f"{prefix}/features.json"])
        self.assertEqual(extraction.line_items[0].amount, "31.50")
        self.assertEqual(extraction.notes, ["Pago a 30 días"])
        self.assertEqual(extraction.uncertainties, ["Firma ilegible", "Sello ilegible"])
        metadata = json.loads(artifacts[f"{prefix}/extraction.json"])
        self.assertEqual(metadata["merged_sha256"], sha256(self.markdown).hexdigest())
        self.assertEqual(metadata["corrections_sha256"], sha256(self.corrections).hexdigest())
        self.assertEqual(metadata["features_sha256"], sha256(artifacts[f"{prefix}/features.json"]).hexdigest())
        self.events.finish.assert_called_once_with(
            self.document.id, self.document.name, "extraction", 1500, f"{prefix}/features.json",
        )
        self.events.save_extraction.assert_called_once_with(self.document.id, self.document.name, extraction)
        self.events.match_entry.assert_called_once_with(self.document, extraction.purchase_order)
        self.assertEqual([call[0] for call in self.events.mock_calls], ["upload", "upload", "save_extraction", "match_entry", "finish"])
        self.client_factory.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1/", api_key="test-key", timeout=180, max_retries=0,
        )
        payload = self.request.call_args.kwargs
        self.assertEqual(payload["messages"][0]["content"],
                         (PROMPTS_DIRECTORY / "extractor.md").read_text(encoding="utf-8").strip())
        self.assertEqual(payload["messages"][1]["content"][0]["text"],
                         "Extract the invoice fields from this combined document:\n\n"
                         "[1] Servicio 31,50 [numeric_tokens: 1=31,50]")
        self.assertIn("[1] Servicio 31,50 [numeric_tokens: 1=31,50]", payload["messages"][1]["content"][0]["text"])
        self.assertEqual(payload["tool_choice"], "required")
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertEqual(payload["tools"][0]["function"]["parameters"], self.result.model_json_schema())
        self.assertEqual(len(payload["tools"]), 1)
        self.assertNotIn("response_format", payload)
        usage = UsageRecord.model_validate_json(self.redis.hset.call_args.args[2])
        self.assertEqual((usage.operation, usage.provider, usage.document_id),
                         ("extraction", "openrouter", str(self.document.id)))
        self.assertEqual(usage.usage[0].cost, Decimal("0.002"))

    def test_invalid_source_reference_fails_without_publishing_extraction_and_keeps_usage(self) -> None:
        self.result.line_items[0].source_line = 2
        self.prepare_response()
        with self.assertRaisesRegex(ValueError, "source references"):
            process(self.document)
        self.events.upload.assert_not_called()
        self.events.save_extraction.assert_not_called()
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once_with(self.document.id, self.document.name, "extraction", 1500)
        usage = UsageRecord.model_validate_json(self.redis.hset.call_args.args[2])
        self.assertEqual(usage.usage[0].cost, Decimal("0.002"))

    def test_storage_failure_never_marks_extraction_ready(self) -> None:
        self.prepare_response()
        self.events.upload.side_effect = ConnectionError("storage")
        with self.assertRaises(ConnectionError):
            process(self.document)
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()
        self.redis.hset.assert_called_once()
        self.events.save_extraction.assert_not_called()

    def test_database_failure_keeps_usage_and_does_not_mark_extraction_ready(self) -> None:
        self.prepare_response()
        self.events.save_extraction.side_effect = ConnectionError("database")
        with self.assertRaises(ConnectionError):
            process(self.document)
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()

    def test_erp_link_failure_does_not_mark_extraction_ready(self) -> None:
        self.prepare_response()
        self.events.match_entry.side_effect = ConnectionError("database")
        with self.assertRaises(ConnectionError):
            process(self.document)
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()
        self.redis.hset.assert_called_once()


class ExtractionWiringTests(unittest.TestCase):
    def test_retry_resumes_extraction_without_pdf_or_previous_model_calls(self) -> None:
        document = queued_document()
        for stage in document.stages[:3]:
            stage.status = "ready"
        with (
            patch("pipeline.runner.bind_snapshot"),
            patch("pipeline.runner.download_file") as download,
            patch("pipeline.runner.process_text") as text,
            patch("pipeline.runner.process_ocr") as ocr,
            patch("pipeline.runner.process_merge") as merge,
            patch("pipeline.runner.process_extraction") as extraction,
        ):
            run_pipeline(document)
        extraction.assert_called_once_with(document)
        download.assert_not_called()
        text.assert_not_called()
        ocr.assert_not_called()
        merge.assert_not_called()

    def test_pending_extraction_is_read_only_and_has_no_invented_extraction(self) -> None:
        document = queued_document()
        for stage in document.stages[:3]:
            stage.status = "ready"
            stage.result_path = stage.stage
        document.stages[3].status = "error"
        document.next_retry_at = document.created_at
        with (
            patch("pipeline.results.download_file", return_value=b"Invoice"),
            patch("pipeline.extraction_4.extraction.create_extractor") as extract,
        ):
            detail = document_detail(document)
            stages = document_stages(document, document.stages)
        self.assertIsNone(detail.extraction)
        self.assertEqual([stage.status for stage in stages], ["ready", "ready", "ready", "retrying"])
        self.assertEqual(stages[3].depends_on, ["merge"])
        extract.assert_not_called()
