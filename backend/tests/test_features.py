import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from extractor.extraction import EXTRACTION_FALLBACK_MODELS, InvoiceExtraction, InvoiceLine, extract_invoice


def extracted_items(items: list[InvoiceLine]) -> InvoiceExtraction:
    return InvoiceExtraction(
        invoice_number="F-1", supplier_name="Proveedor", supplier_nif="B12345678",
        iban="ES123", invoice_date="2026-01-01", purchase_order="PO-2026-0001", currency="EUR",
        line_items=items, tax_base="200.19", vat_rate="21", vat_amount="42.04",
        total="242.23", notes=[], uncertainties=[],
    )


class InvoiceExtractionTests(unittest.TestCase):
    def test_system_prompt_is_loaded_for_each_extraction_without_interpreting_document_braces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prompts = Path(temporary)
            system = prompts / "extractor.md"
            system.write_text("# Role\n\nExtract invoice facts.\n", encoding="utf-8")
            with (
                patch("extractor.extractor.PROMPTS_DIRECTORY", prompts),
                patch("extractor.extraction.create_extractor") as factory,
            ):
                run = factory.return_value.__enter__.return_value.run
                run.return_value = extracted_items([])
                extract_invoice("Nota {document_text}", [b"page"])
                system.write_text("# Role\n\nExtract printed facts only.\n", encoding="utf-8")
                extract_invoice("Nota {document_text}", [b"page"])
        first, second = run.call_args_list
        self.assertEqual(first.args[0], "# Role\n\nExtract invoice facts.")
        self.assertEqual(second.args[0], "# Role\n\nExtract printed facts only.")
        self.assertEqual(second.args[1],
                         'Extract the invoice fields from this raw PDF text and the attached page images: {"native_text": "Nota {document_text}"}')

    def test_normalizes_summary_decimals_without_changing_printed_values(self) -> None:
        extracted = extracted_items([])
        extracted.tax_base = "-1.234,56"
        extracted.vat_rate = "10,5"
        extracted.vat_amount = "-129,63"
        extracted.total = "-1.364,19"
        with patch("extractor.extraction.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted
            result = extract_invoice("Base -1.234,56 IVA 10,5% -129,63 Total -1.364,19", [b"page"])
        self.assertEqual((result.tax_base, result.vat_rate, result.vat_amount, result.total),
                         ("-1234.56", "10.5", "-129.63", "-1364.19"))

    def test_repeated_descriptions_keep_their_own_visually_read_amounts(self) -> None:
        items = [InvoiceLine(description="Suministro", amount="66,73"), InvoiceLine(description="Suministro", amount="133,46")]
        with patch("extractor.extraction.create_extractor") as factory:
            run = factory.return_value.__enter__.return_value.run
            run.return_value = extracted_items(items)
            result = extract_invoice("Suministro 66,73\nSuministro 66,73", [b"page one", b"page two"])
        self.assertEqual([item.amount for item in result.line_items], ["66.73", "133.46"])
        self.assertEqual(run.call_args.kwargs["page_images"], [b"page one", b"page two"])
        self.assertEqual(run.call_args.kwargs["fallback_models"], EXTRACTION_FALLBACK_MODELS)
        self.assertEqual(run.call_args.args[2], InvoiceExtraction)
        run.assert_called_once()

    def test_normalizes_grouping_and_preserves_signed_amounts_without_rounding(self) -> None:
        for printed, expected in [
            ("1 234,56", "1234.56"), ("1\u00a0234,56", "1234.56"), ("1\u202f234,56", "1234.56"),
            ("-1 234 567,89", "-1234567.89"), ("1 234.56", "1234.56"), ("1,234.56", "1234.56"),
            ("-1,234,567.89", "-1234567.89"), ("1.234.567,89", "1234567.89"), ("1.000", "1.000"),
        ]:
            with self.subTest(printed=printed), patch("extractor.extraction.create_extractor") as factory:
                factory.return_value.__enter__.return_value.run.return_value = extracted_items([
                    InvoiceLine(description="Servicio", amount=printed),
                ])
                result = extract_invoice("", [b"image-only invoice"])
                self.assertEqual(result.line_items[0].amount, expected)

    def test_missing_amount_stays_empty_and_uncertainty_is_preserved(self) -> None:
        extracted = extracted_items([InvoiceLine(description="Servicio", amount="")])
        extracted.uncertainties = ["Importe ilegible"]
        with patch("extractor.extraction.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted
            result = extract_invoice("Servicio", [b"page"])
        self.assertEqual(result.line_items[0].amount, "")
        self.assertEqual(result.uncertainties, ["Importe ilegible"])

    def test_currency_and_original_amounts_are_preserved(self) -> None:
        for currency in ("EUR", "USD", "GBP", "CHF", "JPY", "BRL", ""):
            with self.subTest(currency=currency), patch("extractor.extraction.create_extractor") as factory:
                extracted = extracted_items([])
                extracted.currency = currency
                extracted.uncertainties = ["Moneda ambigua"] if currency == "" else []
                factory.return_value.__enter__.return_value.run.return_value = extracted
                result = extract_invoice("", [b"page"])
                self.assertEqual(result.currency, currency)
                self.assertEqual(result.total, extracted.total)
                self.assertEqual(result.uncertainties, extracted.uncertainties)
