import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from invoices.repository import list_incidents
from invoices.router import router


class IncidentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = MagicMock()
        self.database.table.return_value.select.return_value.is_.return_value.execute.return_value.data = [
            {
                "id": "00000000-0000-0000-0000-000000000001", "name": "revisar.pdf",
                "created_at": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc), "invoice_date": "2026-09-01",
                "supplier_nif": "B12345678", "total_eur": "242.00",
                "payment_decision": {
                    "classification": "ESCALAR", "reasons": ["El NIF no coincide con el proveedor."], "checks": {},
                    "due_date": "2026-10-01", "amount_eur": "121.00",
                },
            },
            {
                "id": "00000000-0000-0000-0000-000000000002", "name": "pagar.pdf",
                "created_at": datetime(2026, 9, 19, tzinfo=timezone.utc), "invoice_date": "2026-09-02",
                "payment_decision": {"classification": "PAGAR", "reasons": [], "checks": {}},
            },
            {
                "id": "00000000-0000-0000-0000-000000000003", "name": "sin-decision.pdf",
                "created_at": datetime(2026, 9, 19, tzinfo=timezone.utc), "invoice_date": None,
                "payment_decision": None,
            },
        ]
        self.database.table.return_value.select.return_value.execute.return_value.data = [
            {"tax_id": "B12345678", "payment_terms_days": 45},
        ]
        self.client = patch("invoices.repository.get_client", return_value=self.database)
        self.client.start()
        self.addCleanup(self.client.stop)

    def test_lists_only_escalated_invoices_with_their_rule_reasons(self) -> None:
        incidents = list_incidents()
        self.assertEqual(len(incidents), 1)
        incident = incidents[0]
        self.assertEqual(incident.invoice_name, "revisar.pdf")
        self.assertEqual(incident.invoice_date, date(2026, 9, 1))
        self.assertEqual(incident.due_date, date(2026, 10, 1))
        self.assertEqual(incident.amount_eur, Decimal("121.00"))
        self.assertEqual(incident.reasons, ["El NIF no coincide con el proveedor."])

    def test_endpoint_returns_incidents(self) -> None:
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            response = client.get("/api/invoices/incidents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["invoice_name"], "revisar.pdf")
        self.assertEqual(response.json()[0]["amount_eur"], "121.00")

    def test_reports_every_reason_with_the_rule_that_raised_it(self) -> None:
        decision = self.database.table.return_value.select.return_value.is_.return_value.execute.return_value.data[0]["payment_decision"]
        decision["failures"] = [
            {"rule": "iban", "reason": "El IBAN no coincide con el del proveedor del maestro."},
            {"rule": "payment_notes", "reason": "La nota pide pagar a otra cuenta."},
        ]
        incident = list_incidents()[0]
        self.assertEqual([failure.rule for failure in incident.failures], ["iban", "payment_notes"])
        self.assertEqual(incident.failures[0].reason, "El IBAN no coincide con el del proveedor del maestro.")

    def test_keeps_the_sentence_unlabelled_when_the_decision_predates_rule_pairing(self) -> None:
        incident = list_incidents()[0]
        self.assertEqual([failure.rule for failure in incident.failures], [""])
        self.assertEqual(incident.failures[0].reason, "El NIF no coincide con el proveedor.")

    def test_rebuilds_due_date_and_amount_when_the_decision_omits_them(self) -> None:
        decision = self.database.table.return_value.select.return_value.is_.return_value.execute.return_value.data[0]["payment_decision"]
        del decision["due_date"], decision["amount_eur"]
        incident = list_incidents()[0]
        self.assertEqual(incident.due_date, date(2026, 10, 16))
        self.assertEqual(incident.amount_eur, Decimal("242.00"))

    def test_leaves_due_date_empty_for_a_supplier_outside_the_master(self) -> None:
        row = self.database.table.return_value.select.return_value.is_.return_value.execute.return_value.data[0]
        del row["payment_decision"]["due_date"]
        row["supplier_nif"] = "B99999999"
        self.assertIsNone(list_incidents()[0].due_date)

    def test_keeps_an_escalated_invoice_when_its_issued_date_is_invalid(self) -> None:
        self.database.table.return_value.select.return_value.is_.return_value.execute.return_value.data[0]["invoice_date"] = "31/02/2026"
        incident = list_incidents()[0]
        self.assertIsNone(incident.invoice_date)


if __name__ == "__main__":
    unittest.main()
