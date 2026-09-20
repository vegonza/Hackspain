import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from analytics.repository import analytics_overview


class AnalyticsRepositoryTests(unittest.TestCase):
    def test_reads_the_aggregated_analytics_rpc(self) -> None:
        client = MagicMock()
        client.rpc.return_value.execute.return_value.data = {
            "spending": {
                "total_eur": "171.15",
                "categories": [
                    {"category": "cleaning", "amount_eur": "146.15"},
                    {"category": "transport", "amount_eur": "25.00"},
                ],
            },
            "vat": {"total_eur": "29", "deductible_eur": "21", "foreign_eur": "8"},
            "usage": {
                "average_document_cost_usd": "0.007",
                "operations": [
                    {"operation": "extraction", "average_document_cost_usd": "0.005"},
                    {"operation": "classification", "average_document_cost_usd": "0.0015"},
                    {"operation": "categorization", "average_document_cost_usd": "0.0005"},
                ],
            },
            "processing": {
                "average_duration_ms": "3000",
                "seconds_per_invoice": "0.3",
                "workers": 10,
            },
        }
        with patch("analytics.repository.get_client", return_value=client):
            result = analytics_overview()

        self.assertEqual(result.spending.total_eur, Decimal("171.15"))
        self.assertEqual([item.model_dump(mode="json") for item in result.spending.categories], [
            {"category": "cleaning", "amount_eur": "146.15"},
            {"category": "transport", "amount_eur": "25.00"},
        ])
        self.assertEqual(result.vat.total_eur, Decimal("29"))
        self.assertEqual(result.vat.deductible_eur, Decimal("21"))
        self.assertEqual(result.vat.foreign_eur, Decimal("8"))
        self.assertEqual(result.usage.average_document_cost_usd, Decimal("0.007"))
        self.assertEqual([item.model_dump(mode="json") for item in result.usage.operations], [
            {"operation": "extraction", "average_document_cost_usd": "0.005"},
            {"operation": "classification", "average_document_cost_usd": "0.0015"},
            {"operation": "categorization", "average_document_cost_usd": "0.0005"},
        ])
        self.assertEqual(result.processing.average_duration_ms, Decimal("3000"))
        self.assertEqual(result.processing.seconds_per_invoice, Decimal("0.3"))
        self.assertEqual(result.processing.workers, 10)
        client.rpc.assert_called_once_with("get_analytics_dashboard", {})


if __name__ == "__main__":
    unittest.main()
