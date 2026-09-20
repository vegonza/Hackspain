import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from extractor.categories import MODEL, InvoiceCategory, TAXONOMY, categorize_invoice
from extractor.extraction import InvoiceExtraction, InvoiceLine
from shared.usage import UsageRecord


class InvoiceCategoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.extraction = InvoiceExtraction(
            invoice_number="F-1",
            supplier_name="Proveedor",
            supplier_nif="B12345678",
            iban="ES123",
            invoice_date="2026-09-20",
            purchase_order="PO-1",
            currency="EUR",
            line_items=[
                InvoiceLine(description="Servicio de aseo de oficinas", amount="80"),
                InvoiceLine(description="No bloquear validación automática", amount="0"),
            ],
            tax_base="80",
            vat_rate="21",
            vat_amount="16.8",
            total="96.8",
            notes=[],
            uncertainties=[],
        )
        self.usage = UsageRecord(provider="typesafe", model=MODEL, operation="categorization",
                                 invoice_id="invoice-1", invoice_name="invoice.pdf")

    def test_classifies_every_line_with_one_typed_request_and_records_usage(self) -> None:
        response = SimpleNamespace(
            model=MODEL,
            usage=SimpleNamespace(input_tokens=250),
            choices={
                "line_0": SimpleNamespace(choice="cleaning"),
                "line_1": SimpleNamespace(choice="other"),
            },
        )
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-key"}), patch("extractor.categories.TypeSafeClient") as factory:
            factory.return_value.__enter__.return_value.system_one.return_value = response
            result = categorize_invoice(self.extraction, self.usage)

        self.assertEqual([line.category for line in result.line_items], [InvoiceCategory.CLEANING, InvoiceCategory.OTHER])
        call = factory.return_value.__enter__.return_value.system_one.call_args
        self.assertEqual(call.kwargs["state"]["line_items"], [
            {"index": 0, "description": "Servicio de aseo de oficinas"},
            {"index": 1, "description": "No bloquear validación automática"},
        ])
        self.assertEqual(set(call.kwargs["questions"]), {"line_0", "line_1"})
        self.assertEqual(set(call.kwargs["questions"]["line_0"].criteria), set(TAXONOMY))
        self.assertEqual(self.usage.provider, "typesafe")
        self.assertEqual(self.usage.model, MODEL)
        self.assertEqual(self.usage.usage[0].cost, Decimal("0.000010500"))
        self.assertEqual(self.usage.usage[0].details, {"input_tokens": 250, "line_items": 2})

    def test_empty_invoices_do_not_call_jev(self) -> None:
        extraction = self.extraction.model_copy(update={"line_items": []})
        with patch("extractor.categories.TypeSafeClient") as factory:
            result = categorize_invoice(extraction, self.usage)
        factory.assert_not_called()
        self.assertEqual(result.line_items, [])


if __name__ == "__main__":
    unittest.main()
