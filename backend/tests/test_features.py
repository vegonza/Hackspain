import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from pipeline.extraction_4.features import SourcedInvoiceFeatures, SourcedInvoiceLine, extract_invoice_features


def extracted_items(items: list[SourcedInvoiceLine]) -> SourcedInvoiceFeatures:
    return SourcedInvoiceFeatures(
        invoice_number="F-1", supplier_name="Proveedor", supplier_nif="B12345678",
        iban="ES123", invoice_date="2026-01-01", purchase_order="PO-2026-0001",
        line_items=items, tax_base="200.19", vat_rate="21", vat_amount="42.04",
        total="242.23", notes=[], uncertainties=[],
    )


class SourceGroundingTests(unittest.TestCase):
    def test_system_prompt_is_loaded_for_each_extraction_without_interpreting_document_braces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prompts = Path(temporary)
            system = prompts / "extractor.md"
            system.write_text("# Role\n\nExtract invoice facts.\n", encoding="utf-8")
            with (
                patch("pipeline.extraction_4.extractor.PROMPTS_DIRECTORY", prompts),
                patch("pipeline.extraction_4.features.create_extractor") as factory,
            ):
                run = factory.return_value.__enter__.return_value.run
                run.return_value = extracted_items([])
                extract_invoice_features("Nota {document_text}")
                system.write_text("# Role\n\nExtract printed facts only.\n", encoding="utf-8")
                extract_invoice_features("Nota {document_text}")
        first, second = run.call_args_list
        self.assertEqual(first.args[0], "# Role\n\nExtract invoice facts.")
        self.assertEqual(second.args[0], "# Role\n\nExtract printed facts only.")
        self.assertEqual(second.args[1],
                         "Extract the invoice fields from this combined document:\n\n[1] Nota {document_text} [numeric_tokens: ]")

    def test_normalizes_summary_decimals_without_changing_printed_values(self) -> None:
        extracted = extracted_items([])
        extracted.tax_base = "-1.234,56"
        extracted.vat_rate = "10,5"
        extracted.vat_amount = "-129,63"
        extracted.total = "-1.364,19"
        with patch("pipeline.extraction_4.features.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted
            result = extract_invoice_features("Base -1.234,56 IVA 10,5% -129,63 Total -1.364,19")
        self.assertEqual((result.tax_base, result.vat_rate, result.vat_amount, result.total),
                         ("-1234.56", "10.5", "-129.63", "-1364.19"))

    def test_repeated_descriptions_keep_their_own_amounts(self) -> None:
        items = [
            SourcedInvoiceLine(description="Suministro", amount_token=1, source_line=1),
            SourcedInvoiceLine(description="Suministro", amount_token=1, source_line=2),
        ]
        with patch("pipeline.extraction_4.features.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted_items(items)
            result = extract_invoice_features("Suministro x1 ... 66,73 €\nSuministro x1 ... 133,46 €")
        self.assertEqual([item.amount for item in result.line_items], ["66.73", "133.46"])
        self.assertNotIn("source_line", result.line_items[0].model_dump())

    def test_preserves_grouped_line_amounts_as_single_source_tokens(self) -> None:
        for printed, expected in [
            ("1 234,56", "1234.56"),
            ("1\u00a0234,56", "1234.56"),
            ("1\u202f234,56", "1234.56"),
            ("-1 234 567,89", "-1234567.89"),
            ("1 234.56", "1234.56"),
            ("1,234.56", "1234.56"),
            ("-1,234,567.89", "-1234567.89"),
            ("1.234.567,89", "1234567.89"),
            ("1234.56", "1234.56"),
        ]:
            with self.subTest(printed=printed), patch("pipeline.extraction_4.features.create_extractor") as factory:
                run = factory.return_value.__enter__.return_value.run
                run.return_value = extracted_items([
                    SourcedInvoiceLine(description="Servicio", source_line=1, amount_token=3),
                ])
                result = extract_invoice_features(f"| Servicio | 1 | {printed} | {printed} |")
                self.assertEqual(result.line_items[0].amount, expected)
                self.assertIn(f"[numeric_tokens: 1=1; 2={printed}; 3={printed}]", run.call_args.args[1])

    def test_grouped_amounts_keep_separate_columns_separate(self) -> None:
        for separator in ("  ", "\t", " | "):
            with self.subTest(separator=separator), patch("pipeline.extraction_4.features.create_extractor") as factory:
                factory.return_value.__enter__.return_value.run.return_value = extracted_items([
                    SourcedInvoiceLine(description="Servicio", source_line=1, amount_token=3),
                ])
                result = extract_invoice_features(separator.join(["Servicio", "2", "617,28", "1 234,56"]))
                self.assertEqual(result.line_items[0].amount, "1234.56")

    def test_normalizes_summary_grouping_without_reinterpreting_decimal_precision(self) -> None:
        extracted = extracted_items([])
        extracted.tax_base = "1,234.56"
        extracted.vat_rate = "1.000"
        extracted.vat_amount = "12,35"
        extracted.total = "1\u202f246,91"
        with patch("pipeline.extraction_4.features.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted
            result = extract_invoice_features("Factura")
        self.assertEqual((result.tax_base, result.vat_rate, result.vat_amount, result.total),
                         ("1234.56", "1.000", "12.35", "1246.91"))

    def test_rejects_swapped_source_rows_even_when_sum_would_be_correct(self) -> None:
        items = [
            SourcedInvoiceLine(description="Suministro", amount_token=1, source_line=2),
            SourcedInvoiceLine(description="Suministro", amount_token=1, source_line=1),
        ]
        with patch("pipeline.extraction_4.features.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted_items(items)
            with self.assertRaisesRegex(ValueError, "source references"):
                extract_invoice_features("Suministro x1 ... 66,73 €\nSuministro x1 ... 133,46 €")

    def test_selects_extended_amount_instead_of_quantity_or_unit_price(self) -> None:
        items = [SourcedInvoiceLine(description="Servicio", amount_token=3, source_line=1)]
        with patch("pipeline.extraction_4.features.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted_items(items)
            result = extract_invoice_features("| Servicio | 3 | 10,50 | 31,50 |")
        self.assertEqual(result.line_items[0].amount, "31.50")

    def test_rejects_nonexistent_numeric_token(self) -> None:
        items = [SourcedInvoiceLine(description="Servicio", amount_token=2, source_line=1)]
        with patch("pipeline.extraction_4.features.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted_items(items)
            with self.assertRaisesRegex(ValueError, "amount token is absent"):
                extract_invoice_features("Servicio 10,00")

    def test_preserves_signed_amounts_and_spanish_thousands(self) -> None:
        items = [SourcedInvoiceLine(description="Abono", amount_token=1, source_line=1)]
        with patch("pipeline.extraction_4.features.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted_items(items)
            result = extract_invoice_features("| Abono | -1.234,56 € |")
        self.assertEqual(result.line_items[0].amount, "-1234.56")

    def test_rejects_invented_source_row(self) -> None:
        items = [SourcedInvoiceLine(description="Servicio", amount_token=1, source_line=2)]
        with patch("pipeline.extraction_4.features.create_extractor") as factory:
            factory.return_value.__enter__.return_value.run.return_value = extracted_items(items)
            with self.assertRaisesRegex(ValueError, "source references"):
                extract_invoice_features("Servicio 10,00")


if __name__ == "__main__":
    unittest.main()
