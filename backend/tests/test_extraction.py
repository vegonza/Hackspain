import json
import unittest
from decimal import Decimal
from hashlib import sha256
from unittest.mock import MagicMock, patch

from openai.types.chat import ChatCompletion

from extractor.categories import CategorizedInvoiceExtraction, CategorizedInvoiceLine, InvoiceCategory
from extractor.extraction import InvoiceExtraction, InvoiceLine
from extractor.extractor import PROMPTS_DIRECTORY, inline_schema
from extractor.processor import process
from shared.usage import UsageEntry, UsageRecord
from tests.test_features import extracted_items
from tests.test_extraction_lifecycle import queued_invoice
from suppliers.models import Supplier


class ExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = queued_invoice()
        self.native = b"Native text"
        self.pdf = b"PDF"
        self.pages = [b"jpeg one", b"jpeg two"]
        self.result = extracted_items([InvoiceLine(description="Servicio", amount="31,50")])
        self.result.currency = "USD"
        self.result.uncertainties = ["Firma ilegible"]
        self.result.notes = ["Pago a 30 días"]
        self.events = MagicMock()
        self.suppliers = self.enterContext(patch("extractor.processor.list_suppliers", return_value=[]))
        self.enterContext(patch("extractor.processor.categorize_invoice", side_effect=self.categorize))
        self.enterContext(patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}))
        self.download = self.enterContext(patch("extractor.processor.download_file", return_value=self.pdf))
        self.write_invoice = self.enterContext(patch("extractor.processor.write_invoice"))
        self.enterContext(patch("extractor.processor.extract_text", return_value=self.native.decode("utf-8")))
        self.enterContext(patch("extractor.processor.bind_snapshot"))
        self.render = self.enterContext(patch("extractor.processor.render_pages", return_value=self.pages))
        self.enterContext(patch("extractor.processor.upload_file", self.events.upload))
        self.enterContext(patch("extractor.processor.save_invoice_extraction", self.events.save_extraction))
        self.enterContext(patch("extractor.processor.match_entry", self.events.match_entry))
        self.enterContext(patch("extractor.processor.start_extraction"))
        self.enterContext(patch("extractor.processor.finish_extraction", self.events.finish))
        self.enterContext(patch("extractor.processor.fail_extraction", self.events.fail))
        self.enterContext(patch("extractor.processor.time.perf_counter", side_effect=[10, 11.5]))
        self.redis = self.enterContext(patch("shared.usage.get_redis")).return_value.__enter__.return_value
        self.client_factory = self.enterContext(patch("extractor.extractor.OpenAI"))
        self.request = self.client_factory.return_value.__enter__.return_value.chat.completions.create

    def categorize(self, extraction: InvoiceExtraction, usage: UsageRecord) -> CategorizedInvoiceExtraction:
        usage.provider = "typesafe"
        usage.usage.append(UsageEntry(provider="typesafe", model="jev-1.13.0", cost=Decimal("0.00001"),
                                      details={"input_tokens": 238, "line_items": len(extraction.line_items)}))
        return CategorizedInvoiceExtraction.model_validate({
            **extraction.model_dump(),
            "line_items": [CategorizedInvoiceLine(**line.model_dump(), category=InvoiceCategory.OTHER)
                           for line in extraction.line_items],
        })

    def usage_records(self) -> list[UsageRecord]:
        return [UsageRecord.model_validate_json(call.args[2]) for call in self.redis.hset.call_args_list]

    def prepare_response(self) -> None:
        self.request.return_value = ChatCompletion.model_validate({
            "id": "response-1", "created": 0, "object": "chat.completion", "provider": "Google", "model": "google/gemini-3.8-flash",
            "usage": {"cost": "0.002", "prompt_tokens": 300, "completion_tokens": 120, "total_tokens": 420},
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "InvoiceExtraction", "arguments": self.result.model_dump_json()},
            }]}}],
        })

    def test_direct_extraction_sends_raw_text_and_all_pages_and_saves_artifacts_and_metrics(self) -> None:
        self.prepare_response()
        process(self.document)
        prefix = f"{self.document.id}/extraction"
        self.assertEqual([call.args[0] for call in self.download.call_args_list], [
            f"{self.document.id}/original.pdf",
        ])
        artifacts = {call.args[0]: call.args[1] for call in self.events.upload.call_args_list}
        extraction = CategorizedInvoiceExtraction.model_validate_json(artifacts[f"{prefix}/features.json"])
        self.assertEqual(extraction.line_items[0].amount, "31.50")
        self.assertEqual(extraction.currency, "USD")
        self.assertEqual(extraction.notes, ["Pago a 30 días"])
        self.assertEqual(extraction.uncertainties, ["Firma ilegible"])
        metadata = json.loads(artifacts[f"{prefix}/extraction.json"])
        self.assertEqual(metadata["native_sha256"], sha256(self.native).hexdigest())
        self.assertEqual(metadata["features_sha256"], sha256(artifacts[f"{prefix}/features.json"]).hexdigest())
        self.events.finish.assert_called_once_with(
            self.document.id, self.document.name, 1500, f"{prefix}/features.json",
        )
        self.events.save_extraction.assert_called_once_with(self.document.id, self.document.name, extraction)
        self.events.match_entry.assert_called_once_with(self.document, extraction.purchase_order)
        self.assertEqual([call[0] for call in self.events.mock_calls], ["upload", "upload", "upload", "upload", "upload", "save_extraction", "match_entry", "finish"])
        self.client_factory.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1/", api_key="test-key", timeout=180, max_retries=0,
        )
        payload = self.request.call_args.kwargs
        self.assertEqual(payload["messages"][0]["content"],
                         (PROMPTS_DIRECTORY / "extractor.md").read_text(encoding="utf-8").strip())
        user_content = payload["messages"][1]["content"]
        self.assertIn('"native_text": "Native text"', user_content[0]["text"])
        self.assertEqual(len([part for part in user_content if part["type"] == "image_url"]), 2)
        self.assertEqual(artifacts[f"{prefix}/pages/page-1.jpg"], self.pages[0])
        self.assertEqual(artifacts[f"{prefix}/pages/page-2.jpg"], self.pages[1])
        self.assertEqual(metadata["pdf_sha256"], sha256(self.pdf).hexdigest())
        self.assertEqual(metadata["page_sha256"], [sha256(page).hexdigest() for page in self.pages])
        self.assertEqual(metadata["categorization_model"], "jev-1.13.0")
        self.write_invoice.assert_called_once_with(self.document)
        self.assertEqual(self.document.pages, 2)
        self.assertEqual(payload["model"], "google/gemini-3.8-flash")
        self.assertNotIn("$ref", json.dumps(payload["tools"]))
        line_schema = payload["tools"][0]["function"]["parameters"]["properties"]["line_items"]["items"]
        self.assertEqual(line_schema["type"], "object")
        self.assertEqual(line_schema["required"], ["description", "amount"])
        self.assertEqual(line_schema["properties"]["amount"]["type"], "string")
        self.request.assert_called_once()
        self.assertEqual(payload["tool_choice"], "required")
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertEqual(payload["tools"][0]["function"]["parameters"], inline_schema(self.result.model_json_schema()))
        self.assertEqual(len(payload["tools"]), 1)
        self.assertNotIn("response_format", payload)
        usage = next(record for record in self.usage_records() if record.operation == "extraction")
        self.assertEqual((usage.operation, usage.provider, usage.invoice_id),
                         ("extraction", "Google", str(self.document.id)))
        self.assertEqual(usage.usage[0].cost, Decimal("0.002"))
        category_usage = next(record for record in self.usage_records() if record.operation == "categorization")
        self.assertEqual(category_usage.usage[0].cost, Decimal("0.00001"))

    def test_invalid_tool_output_fails_without_publishing_extraction_and_keeps_usage(self) -> None:
        self.prepare_response()
        self.request.return_value.choices[0].message.tool_calls[0].function.arguments = '{"invoice_number": "F-1"}'
        with self.assertRaises(ValueError):
            process(self.document)
        self.assertEqual([call.args[0] for call in self.events.upload.call_args_list], [
            f"{self.document.id}/native.txt", f"{self.document.id}/extraction/pages/page-1.jpg", f"{self.document.id}/extraction/pages/page-2.jpg",
        ])
        self.events.save_extraction.assert_not_called()
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once_with(self.document.id, self.document.name, 1500)
        usage = UsageRecord.model_validate_json(self.redis.hset.call_args.args[2])
        self.assertEqual(usage.usage[0].cost, Decimal("0.002"))

    def test_identifier_recovery_is_saved_with_its_original_evidence(self) -> None:
        self.result.supplier_nif = 'B96120774'
        self.result.iban = 'ES4414650100951704302211'
        self.suppliers.return_value = [Supplier(
            supplier_id='P1', legal_name='Proveedor', tax_id='B98120774', iban=self.result.iban,
            city='Málaga', payment_terms_days=30,
        )]
        self.prepare_response()
        process(self.document)
        prefix = f'{self.document.id}/extraction'
        artifacts = {call.args[0]: call.args[1] for call in self.events.upload.call_args_list}
        recovered = CategorizedInvoiceExtraction.model_validate_json(artifacts[f'{prefix}/features.json'])
        self.assertEqual(recovered.supplier_nif, 'B98120774')
        self.events.save_extraction.assert_called_once_with(self.document.id, self.document.name, recovered)
        metadata = json.loads(artifacts[f'{prefix}/extraction.json'])
        self.assertEqual(metadata['identifier_corrections'], [{
            'field': 'supplier_nif', 'original': 'B96120774', 'corrected': 'B98120774',
            'supplier_id': 'P1', 'matched_field': 'iban', 'matched_value': self.result.iban,
        }])
        self.assertEqual(metadata['features_sha256'], sha256(artifacts[f'{prefix}/features.json']).hexdigest())

    def test_supplier_lookup_failure_does_not_publish_extraction(self) -> None:
        self.prepare_response()
        self.suppliers.side_effect = ConnectionError('Suppliers unavailable')
        with self.assertRaises(ConnectionError):
            process(self.document)
        self.events.save_extraction.assert_not_called()
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()

    def test_two_character_difference_is_inferred_without_another_model_call(self) -> None:
        self.result.supplier_nif = 'B96120771'
        self.result.iban = 'ES4414650100951704302211'
        self.suppliers.return_value = [Supplier(
            supplier_id='P1', legal_name='Proveedor', tax_id='B98120774', iban=self.result.iban,
            city='Málaga', payment_terms_days=30,
        )]
        self.prepare_response()
        process(self.document)
        self.request.assert_called_once()
        self.assertEqual(self.events.save_extraction.call_args.args[2].supplier_nif, 'B98120774')
        artifacts = {call.args[0]: call.args[1] for call in self.events.upload.call_args_list}
        metadata = json.loads(artifacts[f'{self.document.id}/extraction/extraction.json'])
        self.assertEqual(metadata['identifier_corrections'][0]['original'], 'B96120771')
        self.assertEqual(metadata['identifier_corrections'][0]['corrected'], 'B98120774')
        self.assertNotIn('identifier_reread', metadata)
        self.assertEqual(self.redis.hset.call_count, 2)

    def test_render_failure_does_not_call_the_model_or_publish_extraction(self) -> None:
        self.render.side_effect = ValueError("PDF rendering returned no pages")
        with self.assertRaises(ValueError):
            process(self.document)
        self.request.assert_not_called()
        self.events.upload.assert_called_once_with(f"{self.document.id}/native.txt", self.native, "text/plain; charset=utf-8")
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()

    def test_storage_failure_never_marks_extraction_ready(self) -> None:
        self.prepare_response()
        self.events.upload.side_effect = [None, None, None, ConnectionError("storage")]
        with self.assertRaises(ConnectionError):
            process(self.document)
        self.events.finish.assert_not_called()
        self.events.fail.assert_called_once()
        self.assertEqual(self.redis.hset.call_count, 2)
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
        self.assertEqual(self.redis.hset.call_count, 2)
