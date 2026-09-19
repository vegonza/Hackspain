import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from invoices.repository import InvoiceDetails, write_invoice, start_extraction, finish_extraction, fail_extraction
from invoices.worker import process_invoice
from invoices.router import invoice_detail
from extractor.text import extract_text
from shared.retries import RetryState


def queued_invoice() -> InvoiceDetails:
    return InvoiceDetails(id=uuid4(), name="invoice.pdf", sha256="a" * 64, created_at=datetime.now(timezone.utc))


class ExtractionLifecycleTests(unittest.TestCase):
    def test_result_is_published_on_document_without_separate_phase_records(self) -> None:
        document = queued_invoice()
        with patch("invoices.repository.get_client") as client:
            start_extraction(document.id, document.name)
            finish_extraction(document.id, document.name, 1500, "features.json")
            fail_extraction(document.id, document.name, 1600)
        self.assertTrue(all(call.args == ("documents",) for call in client.return_value.table.call_args_list))
        updates = client.return_value.table.return_value.update.call_args_list
        self.assertIsNone(updates[0].args[0]["result_path"])
        self.assertEqual(updates[1].args[0]["result_path"], "features.json")
        self.assertEqual(updates[1].args[0]["duration_ms"], 1500)
        self.assertEqual(updates[2].args[0]["duration_ms"], 1600)
        self.assertNotIn("result_path", updates[2].args[0])

    def test_worker_completes_only_after_extractor_returns(self) -> None:
        document = queued_invoice()
        statuses: list[str] = []
        def capture(value: InvoiceDetails) -> None:
            statuses.append(value.status)
        with (
            patch("invoices.worker.get_redis"),
            patch("invoices.worker.read_retry", return_value=RetryState()),
            patch("invoices.worker.read_invoice_detail", return_value=document),
            patch("invoices.worker.write_invoice", side_effect=capture),
            patch("invoices.worker.process_invoice_record") as extract,
        ):
            process_invoice(str(document.id))
        extract.assert_called_once_with(document)
        self.assertEqual(statuses, ["processing", "ready"])

    def test_worker_does_not_publish_ready_on_extractor_failure(self) -> None:
        document = queued_invoice()
        with (
            patch("invoices.worker.get_redis"),
            patch("invoices.worker.read_retry", return_value=RetryState()),
            patch("invoices.worker.read_invoice_detail", return_value=document),
            patch("invoices.worker.write_invoice") as write,
            patch("invoices.worker.process_invoice_record", side_effect=ValueError("invalid output")),
        ):
            with self.assertRaises(ValueError):
                process_invoice(str(document.id))
        write.assert_called_once_with(document)
        self.assertEqual(document.status, "processing")

    def test_document_status_updates_do_not_overwrite_extraction_metadata(self) -> None:
        document = queued_invoice()
        document.result_path = "features.json"
        with patch("invoices.repository.get_client") as client:
            write_invoice(document)
        saved = client.return_value.table.return_value.upsert.call_args.args[0]
        self.assertEqual(set(saved), {"id", "name", "sha256", "created_at", "status", "pages"})

    def test_pending_result_never_reads_an_old_artifact(self) -> None:
        document = queued_invoice()
        with patch("invoices.router.download_file") as download:
            detail = invoice_detail(document)
        download.assert_not_called()
        self.assertIsNone(detail.extraction)
        self.assertIsNone(detail.native_text)

    def test_raw_text_preserves_whitespace_and_unusual_content(self) -> None:
        raw = "  Hidden layer\n  Texto   31,50\f\n".encode("utf-8")
        with patch("extractor.text.subprocess.run") as command:
            command.return_value.stdout = raw
            self.assertEqual(extract_text(b"PDF"), raw.decode("utf-8"))
        command.assert_called_once_with(["pdftotext", "-layout", "-", "-"], input=b"PDF", capture_output=True, check=True)

    def test_new_invoice_is_extracted_before_classification(self) -> None:
        from invoices.processing import process
        invoice = queued_invoice()
        events = MagicMock()
        with patch("invoices.processing.extract_invoice", events.extract), patch("invoices.processing.classify_invoice", events.classify):
            process(invoice)
        self.assertEqual([call[0] for call in events.mock_calls], ["extract", "classify"])

    def test_classification_retry_reuses_saved_extraction(self) -> None:
        from invoices.processing import process
        invoice = queued_invoice()
        invoice.result_path = f"{invoice.id}/extraction/features.json"
        with patch("invoices.processing.extract_invoice") as extract, patch("invoices.processing.classify_invoice") as classify:
            process(invoice)
        extract.assert_not_called()
        classify.assert_called_once_with(invoice)

    def test_extraction_failure_prevents_classification(self) -> None:
        from invoices.processing import process
        invoice = queued_invoice()
        with patch("invoices.processing.extract_invoice", side_effect=ValueError("Unreadable PDF")), patch("invoices.processing.classify_invoice") as classify:
            with self.assertRaises(ValueError):
                process(invoice)
        classify.assert_not_called()
