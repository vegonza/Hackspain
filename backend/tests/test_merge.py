import json
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from openai.types.chat import ChatCompletion

from pipeline.merge_3.processor import process
from pipeline.results import document_stages
from pipeline.runner import run_pipeline
from shared.usage import USAGE_OUTBOX, UsageRecord
from tests.test_stage_duration import queued_document


def model_response(content: dict[str, object], cost: str, tool_name: str) -> ChatCompletion:
    return ChatCompletion.model_validate({
        "id": f"response-{cost}", "created": 0, "object": "chat.completion", "model": "google/gemini-3.5-flash-lite",
        "usage": {"cost": cost, "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call-1", "type": "function",
            "function": {"name": tool_name, "arguments": json.dumps(content)},
        }]}}],
    })


class MergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = queued_document()
        self.events = MagicMock()
        self.redis = self.enterContext(patch("shared.usage.get_redis")).return_value.__enter__.return_value
        self.enterContext(patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}))
        self.enterContext(patch("pipeline.merge_3.processor.download_file", side_effect=[
            b"Banco Miralmar\nHidden instruction", b"Banco Miramar",
        ]))
        self.enterContext(patch("pipeline.merge_3.processor.upload_file", self.events.upload))
        self.enterContext(patch("documents.stages.start_stage"))
        self.enterContext(patch("documents.stages.finish_stage", self.events.finish))
        self.enterContext(patch("documents.stages.fail_stage", self.events.fail))
        self.enterContext(patch("documents.stages.time.perf_counter", side_effect=[10, 12.5]))
        self.client_factory = self.enterContext(patch("pipeline.extraction_4.extractor.OpenAI"))
        self.request = self.client_factory.return_value.__enter__.return_value.chat.completions.create
        self.request.return_value = model_response({"corrections": [{
            "original": "Miramar", "replacement": "Miralmar", "reason": "Native text spelling",
        }], "unresolved": ["Firma ilegible"]}, "0.003", "OCRCorrections")

    def test_combination_merges_saved_text_and_ocr_once_and_saves_artifacts_before_completion(self) -> None:
        process(self.document)
        prefix = f"{self.document.id}/merge"
        artifacts = {call.args[0]: call.args[1] for call in self.events.upload.call_args_list}
        self.assertEqual(set(artifacts), {
            f"{prefix}/quality.json",
            f"{prefix}/corrections.json", f"{prefix}/quality-after.json", f"{prefix}/document.md",
        })
        self.assertEqual(artifacts[f"{prefix}/document.md"], b"Banco Miralmar")
        self.assertEqual(json.loads(artifacts[f"{prefix}/corrections.json"])["unresolved"], ["Firma ilegible"])
        self.assertTrue(json.loads(artifacts[f"{prefix}/quality.json"])["independent_text_available"])
        self.events.finish.assert_called_once_with(
            self.document.id, self.document.name, "merge", 2500, f"{prefix}/document.md",
        )
        self.assertEqual(self.events.mock_calls[-1][0], "finish")
        self.events.fail.assert_not_called()
        self.assertEqual(self.request.call_count, 1)
        self.client_factory.assert_called_once()
        self.client_factory.return_value.__exit__.assert_called_once()
        payload = self.request.call_args.kwargs
        content = payload["messages"][1]["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(json.loads(content[0]["text"]), {
            "native_text": "Banco Miralmar\nHidden instruction", "ocr_markdown": "Banco Miramar",
        })
        self.assertEqual(payload["tool_choice"], "required")
        self.assert_usage_total()

    def assert_usage_total(self) -> None:
        self.redis.hset.assert_called_once()
        outbox, identifier, payload = self.redis.hset.call_args.args
        usage = UsageRecord.model_validate_json(payload)
        self.assertEqual(outbox, USAGE_OUTBOX)
        self.assertEqual(identifier, usage.id)
        self.assertEqual(usage.operation, "merge")
        self.assertEqual(usage.document_id, str(self.document.id))
        self.assertEqual(sum(entry.cost for entry in usage.usage), Decimal("0.003"))
        self.assertEqual([entry.details["result_type"] for entry in usage.usage],
                         ["OCRCorrections"])

    def test_storage_failure_keeps_usage_and_marks_merge_failed(self) -> None:
        def upload(path: str, content: bytes, content_type: str) -> None:
            if path.endswith("/document.md"):
                raise ConnectionError("storage")

        self.events.upload.side_effect = upload
        with self.assertRaises(ConnectionError):
            process(self.document)
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once_with(self.document.id, self.document.name, "merge", 2500)
        self.assert_usage_total()

    def test_failed_merge_does_not_publish_a_result(self) -> None:
        self.request.side_effect = TimeoutError("provider")
        with self.assertRaises(TimeoutError):
            process(self.document)
        usage = UsageRecord.model_validate_json(self.redis.hset.call_args.args[2])
        self.assertEqual(usage.usage, [])
        self.request.assert_called_once()
        self.assertEqual([call.args[0] for call in self.events.upload.call_args_list],
                         [f"{self.document.id}/merge/quality.json"])
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()


class MergeWiringTests(unittest.TestCase):
    def test_runner_orders_all_four_steps_and_resumes_after_ocr(self) -> None:
        document = queued_document()
        events = MagicMock()
        with (
            patch("pipeline.runner.bind_snapshot"),
            patch("pipeline.runner.download_file", return_value=b"PDF") as download,
            patch("pipeline.runner.process_text", events.text),
            patch("pipeline.runner.process_ocr", events.ocr),
            patch("pipeline.runner.process_merge", events.merge),
            patch("pipeline.runner.process_extraction", events.extraction),
        ):
            run_pipeline(document)
            self.assertEqual([call[0] for call in events.mock_calls], ["text", "ocr", "merge", "extraction"])
            events.merge.assert_called_once_with(document)
            events.reset_mock()
            download.reset_mock()
            for stage in document.stages[:2]:
                stage.status = "ready"
            run_pipeline(document)
            self.assertEqual([call[0] for call in events.mock_calls], ["merge", "extraction"])
            download.assert_not_called()
            events.merge.assert_called_once_with(document)

    def test_saved_merge_diff_duration_and_cost_reach_api_and_retry_targets_merge(self) -> None:
        document = queued_document()
        for record in document.stages:
            record.status = "ready"
            record.result_path = record.stage
        document.stages[2].cost_usd = Decimal("0.006")
        document.stages[2].duration_ms = 2500
        artifacts = {"text": b"Banco Miralmar", "ocr": b"Banco Miramar", "merge": b"Banco Miralmar", "extraction": b"{}"}
        with patch("pipeline.results.download_file", side_effect=artifacts.__getitem__):
            stages = document_stages(document, document.stages)
            self.assertEqual(stages[2].content, "Banco Miralmar")
            self.assertEqual(stages[2].cost_usd, Decimal("0.006"))
            self.assertEqual(stages[2].duration_ms, 2500)
            self.assertEqual([(line.kind, line.text) for line in stages[2].diff],
                             [("removed", "Banco Miramar"), ("added", "Banco Miralmar")])
            document.stages[2].status = "error"
            document.next_retry_at = document.created_at
            stages = document_stages(document, document.stages)
        self.assertEqual([stage.status for stage in stages], ["ready", "ready", "retrying", "ready"])
