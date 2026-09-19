import json
import unittest
from decimal import Decimal
from hashlib import sha256
from unittest.mock import MagicMock, patch

from openai.types.chat import ChatCompletion

from invoices.router import invoice_detail
from pipeline.extraction_3.extraction import InvoiceExtraction, InvoiceLine
from pipeline.extraction_3.extractor import PROMPTS_DIRECTORY
from pipeline.extraction_3.processor import process
from pipeline.results import invoice_stages
from pipeline.runner import run_pipeline
from shared.usage import UsageRecord
from tests.test_features import extracted_items
from tests.test_stage_duration import queued_invoice


class ExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.invoice_record = queued_invoice()
        self.markdown = b"Servicio 31,50"
        self.native = b"Native text"
        self.pdf = b"PDF"
        self.pages = [b"jpeg one", b"jpeg two"]
        self.result = extracted_items([InvoiceLine(description="Servicio", amount="31,50")])
        self.result.uncertainties = ["Firma ilegible"]
        self.result.notes = ["Pago a 30 días"]
        self.events = MagicMock()
        self.enterContext(patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}))
        self.download = self.enterContext(patch("pipeline.extraction_3.processor.download_file", side_effect=[
            self.native, self.markdown, self.pdf,
        ]))
        self.render = self.enterContext(patch("pipeline.extraction_3.processor.render_pages", return_value=self.pages))
        self.enterContext(patch("pipeline.extraction_3.processor.upload_file", self.events.upload))
        self.enterContext(patch("pipeline.extraction_3.processor.save_invoice_extraction", self.events.save_extraction))
        self.enterContext(patch("pipeline.extraction_3.processor.match_entry", self.events.match_entry))
        self.enterContext(patch("invoices.stages.start_stage"))
        self.enterContext(patch("invoices.stages.finish_stage", self.events.finish))
        self.enterContext(patch("invoices.stages.fail_stage", self.events.fail))
        self.enterContext(patch("invoices.stages.time.perf_counter", side_effect=[10, 11.5]))
        self.redis = self.enterContext(patch("shared.usage.get_redis")).return_value.__enter__.return_value
        self.client_factory = self.enterContext(patch("pipeline.extraction_3.extractor.OpenAI"))
        self.request = self.client_factory.return_value.__enter__.return_value.chat.completions.create

    def prepare_response(self) -> None:
        self.request.return_value = ChatCompletion.model_validate({
            "id": "response-1", "provider": "Google", "created": 0, "object": "chat.completion", "model": "google/gemini-3.5-flash-lite",
            "usage": {"cost": "0.002", "prompt_tokens": 300, "completion_tokens": 120, "total_tokens": 420},
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "InvoiceExtraction", "arguments": self.result.model_dump_json()},
            }]}}],
        })

    def test_direct_extraction_sends_both_texts_and_all_pages_and_saves_artifacts_and_metrics(self) -> None:
        self.prepare_response()
        process(self.invoice_record)
        prefix = f"{self.invoice_record.id}/extraction"
        self.assertEqual([call.args[0] for call in self.download.call_args_list], [
            f"{self.invoice_record.id}/native.txt", f"{self.invoice_record.id}/document.md", f"{self.invoice_record.id}/original.pdf",
        ])
        artifacts = {call.args[0]: call.args[1] for call in self.events.upload.call_args_list}
        extraction = InvoiceExtraction.model_validate_json(artifacts[f"{prefix}/features.json"])
        self.assertEqual(extraction.line_items[0].amount, "31.50")
        self.assertEqual(extraction.notes, ["Pago a 30 días"])
        self.assertEqual(extraction.uncertainties, ["Firma ilegible"])
        metadata = json.loads(artifacts[f"{prefix}/extraction.json"])
        self.assertEqual(metadata["ocr_sha256"], sha256(self.markdown).hexdigest())
        self.assertEqual(metadata["native_sha256"], sha256(self.native).hexdigest())
        self.assertEqual(metadata["features_sha256"], sha256(artifacts[f"{prefix}/features.json"]).hexdigest())
        self.events.finish.assert_called_once_with(
            self.invoice_record.id, self.invoice_record.name, "extraction", 1500, f"{prefix}/features.json",
        )
        self.events.save_extraction.assert_called_once_with(self.invoice_record.id, self.invoice_record.name, extraction)
        self.events.match_entry.assert_called_once_with(self.invoice_record, extraction.purchase_order)
        self.assertEqual([call[0] for call in self.events.mock_calls], ["upload", "upload", "upload", "upload", "save_extraction", "match_entry", "finish"])
        self.client_factory.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1/", api_key="test-key", timeout=180, max_retries=0,
        )
        payload = self.request.call_args.kwargs
        self.assertEqual(payload["messages"][0]["content"],
                         (PROMPTS_DIRECTORY / "extractor.md").read_text(encoding="utf-8").strip())
        user_content = payload["messages"][1]["content"]
        self.assertIn('"native_text": "Native text"', user_content[0]["text"])
        self.assertIn('"ocr_markdown": "Servicio 31,50"', user_content[0]["text"])
        self.assertEqual(len([part for part in user_content if part["type"] == "image_url"]), 2)
        self.assertEqual(artifacts[f"{prefix}/pages/page-1.jpg"], self.pages[0])
        self.assertEqual(artifacts[f"{prefix}/pages/page-2.jpg"], self.pages[1])
        self.assertEqual(metadata["pdf_sha256"], sha256(self.pdf).hexdigest())
        self.assertEqual(metadata["page_sha256"], [sha256(page).hexdigest() for page in self.pages])
        self.request.assert_called_once()
        self.assertEqual(payload["tool_choice"], "required")
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertEqual(payload["tools"][0]["function"]["parameters"], self.result.model_json_schema())
        self.assertEqual(len(payload["tools"]), 1)
        self.assertNotIn("response_format", payload)
        usage = UsageRecord.model_validate_json(self.redis.hset.call_args.args[2])
        self.assertEqual((usage.operation, usage.provider, usage.invoice_id),
                         ("extraction", "Google", str(self.invoice_record.id)))
        self.assertEqual(usage.usage[0].cost, Decimal("0.002"))

    def test_invalid_tool_output_fails_without_publishing_extraction_and_keeps_usage(self) -> None:
        self.prepare_response()
        self.request.return_value.choices[0].message.tool_calls[0].function.arguments = '{"invoice_number": "F-1"}'
        with self.assertRaises(ValueError):
            process(self.invoice_record)
        self.assertEqual([call.args[0] for call in self.events.upload.call_args_list], [
            f"{self.invoice_record.id}/extraction/pages/page-1.jpg", f"{self.invoice_record.id}/extraction/pages/page-2.jpg",
        ])
        self.events.save_extraction.assert_not_called()
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once_with(self.invoice_record.id, self.invoice_record.name, "extraction", 1500)
        usage = UsageRecord.model_validate_json(self.redis.hset.call_args.args[2])
        self.assertEqual(usage.usage[0].cost, Decimal("0.002"))

    def test_render_failure_does_not_call_the_model_or_publish_extraction(self) -> None:
        self.render.side_effect = ValueError("PDF rendering returned no pages")
        with self.assertRaises(ValueError):
            process(self.invoice_record)
        self.request.assert_not_called()
        self.events.upload.assert_not_called()
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()

    def test_storage_failure_never_marks_extraction_ready(self) -> None:
        self.prepare_response()
        self.events.upload.side_effect = [None, None, ConnectionError("storage")]
        with self.assertRaises(ConnectionError):
            process(self.invoice_record)
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()
        self.redis.hset.assert_called_once()
        self.events.save_extraction.assert_not_called()

    def test_database_failure_keeps_usage_and_does_not_mark_extraction_ready(self) -> None:
        self.prepare_response()
        self.events.save_extraction.side_effect = ConnectionError("database")
        with self.assertRaises(ConnectionError):
            process(self.invoice_record)
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()

    def test_erp_link_failure_does_not_mark_extraction_ready(self) -> None:
        self.prepare_response()
        self.events.match_entry.side_effect = ConnectionError("database")
        with self.assertRaises(ConnectionError):
            process(self.invoice_record)
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()
        self.redis.hset.assert_called_once()


class ExtractionWiringTests(unittest.TestCase):
    def test_retry_resumes_extraction_without_rerunning_text_or_ocr(self) -> None:
        invoice_record = queued_invoice()
        for stage in invoice_record.stages[:2]:
            stage.status = "ready"
        with (
            patch("pipeline.runner.bind_snapshot"),
            patch("pipeline.runner.download_file") as download,
            patch("pipeline.runner.process_text") as text,
            patch("pipeline.runner.process_ocr") as ocr,
            patch("pipeline.runner.process_extraction") as extraction,
            patch("pipeline.runner.process_classification") as classification,
        ):
            run_pipeline(invoice_record)
        extraction.assert_called_once_with(invoice_record)
        classification.assert_called_once_with(invoice_record)
        download.assert_not_called()
        text.assert_not_called()
        ocr.assert_not_called()

    def test_pending_extraction_is_read_only_and_has_no_invented_extraction(self) -> None:
        invoice_record = queued_invoice()
        for stage in invoice_record.stages[:2]:
            stage.status = "ready"
            stage.result_path = stage.stage
        invoice_record.stages[2].status = "error"
        invoice_record.next_retry_at = invoice_record.created_at
        with (
            patch("pipeline.results.download_file", return_value=b"Invoice"),
            patch("pipeline.extraction_3.extraction.create_extractor") as extract,
        ):
            detail = invoice_detail(invoice_record)
            stages = invoice_stages(invoice_record, invoice_record.stages)
        self.assertIsNone(detail.extraction)
        self.assertEqual([stage.status for stage in stages], ["ready", "ready", "retrying"])
        self.assertEqual(stages[2].depends_on, ["ocr", "text"])
        extract.assert_not_called()
