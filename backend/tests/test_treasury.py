import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from treasury.models import SupplierCommitment, TreasuryPayment, TreasuryReport, TreasurySummary
from treasury.repository import read_treasury
from treasury.router import router


class TreasuryTests(unittest.TestCase):
    def test_summarizes_payment_windows_review_risk_and_suppliers(self) -> None:
        database = MagicMock()
        database.table.return_value.select.return_value.is_.return_value.execute.return_value.data = [
            {"id": "00000000-0000-0000-0000-000000000001", "name": "alfa-1.pdf", "payment_decision": {"classification": "PAGAR", "reasons": [], "checks": {}, "due_date": "2026-09-20", "amount_eur": "100.25", "supplier_name": "Alfa"}},
            {"id": "00000000-0000-0000-0000-000000000002", "name": "alfa-2.pdf", "payment_decision": {"classification": "PAGAR", "reasons": [], "checks": {}, "due_date": "2026-09-29", "amount_eur": "200.50", "supplier_name": "Alfa"}},
            {"id": "00000000-0000-0000-0000-000000000003", "name": "beta-1.pdf", "payment_decision": {"classification": "PAGAR", "reasons": [], "checks": {}, "due_date": "2026-10-10", "amount_eur": "300.75", "supplier_name": "Beta"}},
            {"id": "00000000-0000-0000-0000-000000000004", "name": "beta-2.pdf", "payment_decision": {"classification": "PAGAR", "reasons": [], "checks": {}, "due_date": "2026-10-30", "amount_eur": "400.00", "supplier_name": "Beta"}},
            {"id": "00000000-0000-0000-0000-000000000005", "name": "gamma.pdf", "payment_decision": {"classification": "ESCALAR", "reasons": [], "checks": {}, "due_date": "2026-09-22", "amount_eur": "50.10", "supplier_name": "Gamma"}},
            {"id": "00000000-0000-0000-0000-000000000006", "name": "pagada.pdf", "payment_decision": {"classification": "NO_PAGAR", "reasons": [], "checks": {}}},
            {"id": "00000000-0000-0000-0000-000000000007", "name": "sin-clasificar.pdf", "payment_decision": None},
            {"id": "00000000-0000-0000-0000-000000000008", "name": "decision-antigua.pdf", "payment_decision": {"classification": "PAGAR", "reasons": [], "checks": {}}},
        ]
        with patch("treasury.repository.get_client", return_value=database):
            report = read_treasury(date(2026, 9, 19))
        self.assertEqual(str(report.summary.next_7_days), "100.25")
        self.assertEqual(str(report.summary.next_30_days), "601.50")
        self.assertEqual(str(report.summary.blocked_in_review), "50.10")
        self.assertEqual([row.supplier_name for row in report.by_supplier], ["Alfa", "Beta"])
        self.assertEqual(report.by_supplier[0].approved_invoices, 2)
        self.assertEqual(str(report.by_supplier[0].committed_amount), "300.75")
        self.assertEqual(report.by_supplier[0].next_due_date, date(2026, 9, 20))
        self.assertEqual([payment.document_name for payment in report.payments], [
            "alfa-1.pdf", "alfa-2.pdf", "beta-1.pdf", "beta-2.pdf",
        ])
        self.assertEqual(str(report.payments[0].amount), "100.25")

    def test_endpoint_returns_decimal_amounts_without_losing_precision(self) -> None:
        report = TreasuryReport(
            summary=TreasurySummary(next_7_days="100.25", next_30_days="300.75", blocked_in_review="50.10"),
            by_supplier=[SupplierCommitment(
                supplier_name="Alfa", approved_invoices=2,
                committed_amount="300.75", next_due_date=date(2026, 9, 20),
            )],
            payments=[TreasuryPayment(
                document_id="00000000-0000-0000-0000-000000000001",
                document_name="alfa-1.pdf", supplier_name="Alfa",
                amount="100.25", due_date=date(2026, 9, 20),
            )],
        )
        app = FastAPI()
        app.include_router(router)
        with patch("treasury.router.read_treasury", return_value=report), TestClient(app) as client:
            response = client.get("/api/treasury")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["next_7_days"], "100.25")
        self.assertEqual(response.json()["by_supplier"][0]["committed_amount"], "300.75")
        self.assertEqual(response.json()["payments"][0]["document_name"], "alfa-1.pdf")


if __name__ == "__main__":
    unittest.main()
