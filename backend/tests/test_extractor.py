import json
import unittest
from decimal import Decimal
from unittest.mock import patch

import httpx2
from openai import InternalServerError, OpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

from pipeline.extraction_4.extractor import MODEL, ExtractionManager, create_extractor
from shared.usage import UsageRecord


class ExtractedText(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


def tool_call(arguments: str, name: str = "ExtractedText") -> dict[str, object]:
    return {"id": "call-1", "type": "function", "function": {"name": name, "arguments": arguments}}


def response(calls: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "response-1", "model": MODEL, "created": 0, "object": "chat.completion",
        "usage": {"cost": "0.001", "prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
        "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": '{"text":"unused prose"}', "tool_calls": calls,
        }}],
    }


class RequiredOutputToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[httpx2.Request] = []
        self.response_body = response([tool_call('{"text":"Factura"}')])
        self.status_code = 200
        client = self.enterContext(OpenAI(
            api_key="test-key", base_url="https://openrouter.ai/api/v1/", max_retries=0,
            http_client=httpx2.Client(transport=httpx2.MockTransport(self.respond)),
        ))
        self.manager = ExtractionManager(client)
        self.usage = UsageRecord(provider="openrouter", model=MODEL, operation="extraction",
                                 document_id="document-1", document_name="invoice.pdf")

    def respond(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(self.status_code, json=self.response_body)

    def test_single_non_streaming_required_tool_uses_sdk_arguments_and_usage(self) -> None:
        result = self.manager.run("Read the invoice", "Document text", ExtractedText, usage=self.usage)
        self.assertEqual(result.text, "Factura")
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        payload = json.loads(request.content)
        self.assertEqual(str(request.url), "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(request.headers["authorization"], "Bearer test-key")
        self.assertEqual(payload["tool_choice"], "required")
        self.assertEqual(payload["usage"], {"include": True})
        self.assertNotIn("provider", payload)
        self.assertNotIn("temperature", payload)
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertNotIn("response_format", payload)
        self.assertEqual(len(payload["tools"]), 1)
        self.assertEqual(payload["tools"][0]["function"]["name"], "ExtractedText")
        self.assertNotIn("strict", payload["tools"][0]["function"])
        self.assertEqual(payload["tools"][0]["function"]["parameters"], ExtractedText.model_json_schema())
        self.assertEqual(payload["messages"][1]["content"], [{"type": "text", "text": "Document text"}])
        self.assertEqual(self.usage.usage[0].cost, Decimal("0.001"))

    def test_requires_exactly_one_call_without_using_message_content_or_making_another_request(self) -> None:
        for calls in ([], [tool_call('{"text":"One"}'), tool_call('{"text":"Two"}')]):
            with self.subTest(calls=len(calls)):
                self.requests.clear()
                self.response_body = response(calls)
                with self.assertRaises(ValueError):
                    self.manager.run("Read", "Text", ExtractedText)
                self.assertEqual(len(self.requests), 1)

    def test_rejects_an_unexpected_output_tool(self) -> None:
        self.response_body = response([tool_call('{"text":"Factura"}', "WrongTool")])
        with self.assertRaisesRegex(ValueError, "Unexpected output tool"):
            self.manager.run("Read", "Text", ExtractedText)
        self.assertEqual(len(self.requests), 1)

    def test_invalid_arguments_fail_schema_validation_and_preserve_billed_usage(self) -> None:
        self.response_body = response([tool_call('{"invented":"Factura"}')])
        with self.assertRaises(ValidationError):
            self.manager.run("Read", "Text", ExtractedText, usage=self.usage)
        self.assertEqual(self.usage.usage[0].cost, Decimal("0.001"))
        self.assertEqual(len(self.requests), 1)

    def test_provider_error_does_not_trigger_sdk_retries(self) -> None:
        self.status_code = 500
        self.response_body = {"error": {"message": "Provider unavailable", "type": "server_error"}}
        with self.assertRaises(InternalServerError):
            self.manager.run("Read", "Text", ExtractedText)
        self.assertEqual(len(self.requests), 1)

    def test_factory_injects_configured_sdk_client_and_closes_it_on_failure(self) -> None:
        with (
            patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}),
            patch("pipeline.extraction_4.extractor.OpenAI") as client_factory,
        ):
            with self.assertRaisesRegex(ValueError, "failed run"):
                with create_extractor() as manager:
                    self.assertIs(manager.client, client_factory.return_value.__enter__.return_value)
                    raise ValueError("failed run")
        client_factory.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1/", api_key="test-key", timeout=180, max_retries=0,
        )
        client_factory.return_value.__exit__.assert_called_once()
