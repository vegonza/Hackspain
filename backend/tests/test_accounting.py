import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from accounting.export import accounting_csv
from accounting.models import AccountingReport
from accounting.repository import read_accounting
from accounting.router import router


def decision(classification: str) -> dict[str, object]:
    return {"classification": classification, "reasons": [], "checks": {}}


def invoice_row(
    identifier: int, description: str, invoice_date: str, tax_base: str, vat_rate: str,
    vat_amount: str, total: str, classification: str = "PAGAR",
) -> dict[str, object]:
    return {
        "id": f"00000000-0000-0000-0000-{identifier:012d}",
        "name": f"factura-{identifier}.pdf",
        "invoice_number": f"F-{identifier}",
        "invoice_date": invoice_date,
        "supplier_name": f"Proveedor {identifier}",
        "supplier_nif": f"B{identifier:08d}",
        "line_items": [{"description": description, "amount": tax_base}],
        "tax_base": tax_base,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total": total,
        "payment_decision": decision(classification),
    }


class AccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            invoice_row(1, "Material de oficina", "2026-07-03", "100", "21", "21", "121"),
            invoice_row(2, "Combustible vehículo", "2026-08-04", "50", "21", "10.50", "60.50"),
            invoice_row(3, "Consultoría", "2026-09-05", "100", "21", "21", "121", "ESCALAR"),
            invoice_row(4, "Seguro anual", "2026-09-06", "80", "0", "0", "80", "NO_PAGAR"),
            invoice_row(5, "Material", "2025-09-06", "20", "21", "4.20", "24.20"),
        ]
        database = MagicMock()
        database.table.return_value.select.return_value.is_.return_value.execute.return_value.data = self.rows
        self.client = patch("accounting.repository.get_client", return_value=database)
        self.client.start()
        self.addCleanup(self.client.stop)

    def test_prepares_safe_expenses_and_escalates_sensitive_or_unresolved_invoices(self) -> None:
        report = read_accounting(2026, 3)
        self.assertEqual(len(report.invoices), 4)
        self.assertEqual(report.summary.recorded_expenses, Decimal("330"))
        self.assertEqual(report.summary.potential_deductible_expenses, Decimal("180"))
        self.assertEqual(report.summary.potential_deductible_vat, Decimal("21"))
        self.assertEqual(report.summary.amount_under_review, Decimal("181.50"))
        self.assertEqual((report.summary.prepared_invoices, report.summary.review_invoices), (2, 2))
        by_name = {invoice.document_name: invoice for invoice in report.invoices}
        self.assertEqual(by_name["factura-1.pdf"].category, "supplies")
        self.assertEqual(by_name["factura-1.pdf"].account_code, "602")
        self.assertEqual(by_name["factura-1.pdf"].status, "PREPARED")
        self.assertEqual(by_name["factura-2.pdf"].review_reasons, ["sensitive_category"])
        self.assertEqual(by_name["factura-3.pdf"].review_reasons, ["payment_review"])
        self.assertEqual(by_name["factura-4.pdf"].status, "PREPARED")

    def test_detects_missing_identity_and_invalid_tax_arithmetic(self) -> None:
        row = invoice_row(6, "Material", "2026-09-07", "100", "21", "20", "121")
        row["supplier_nif"] = None
        self.rows[:] = [row]
        invoice = read_accounting(2026, None).invoices[0]
        self.assertEqual(invoice.status, "REVIEW")
        self.assertEqual(invoice.review_reasons, ["missing_identity", "invalid_tax_amounts"])
        self.assertEqual(invoice.potential_deductible_vat, Decimal(0))

    def test_csv_is_excel_friendly_and_keeps_audit_fields(self) -> None:
        content = accounting_csv(read_accounting(2026, 3)).decode("utf-8")
        self.assertTrue(content.startswith("\ufeffDocumento;Número de factura;Fecha"))
        self.assertIn("factura-2.pdf;F-2;2026-08-04", content)
        self.assertIn("REVIEW;sensitive_category", content)

    def test_endpoint_and_export_validate_the_requested_period(self) -> None:
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.get("/api/accounting?year=2026&quarter=3")
            exported = client.get("/api/accounting/export?year=2026&quarter=3")
            invalid = client.get("/api/accounting?year=2026&quarter=5")
        self.assertEqual(response.status_code, 200)
        report = AccountingReport.model_validate(response.json())
        self.assertEqual(report.quarter, 3)
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("precierre-fiscal-2026-t3.csv", exported.headers["content-disposition"])
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
