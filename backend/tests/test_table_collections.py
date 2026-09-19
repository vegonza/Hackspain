import unittest
from unittest.mock import MagicMock, call, patch
from uuid import UUID

from suppliers.repository import list_suppliers
from usage.router import get_usage


class TableCollectionsTests(unittest.TestCase):
    def test_usage_returns_only_the_requested_database_page(self) -> None:
        records = [{
            "id": str(UUID(int=index + 1)), "created_at": "2026-09-19T14:00:00Z",
            "provider": "openrouter", "model": "extraction", "operation": "extraction",
            "document_id": str(UUID(int=1)), "document_name": "invoice.pdf", "usage": [],
        } for index in range(1100)]
        client = MagicMock()
        for page in (0, 1, 43, 44):
            with self.subTest(page=page):
                client.reset_mock()
                expected = records[page * 25:(page + 1) * 25]
                client.rpc.return_value.execute.return_value.data = {
                    "records": expected, "total": 1100, "page_size": 25, "daily": [],
                    "summary": {"calls": 1100, "pages": 1100, "cost_usd": "4.4", "average_document_cost_usd": "4.4"},
                }
                with patch("usage.router.get_client", return_value=client), patch("usage.router.get_redis") as redis:
                    redis.return_value.__enter__.return_value.hvals.return_value = []
                    result = get_usage(page)
                client.rpc.assert_called_once_with("get_usage_dashboard", {"p_page": page})
                client.table.assert_not_called()
                self.assertEqual([record.id for record in result.records], [record["id"] for record in expected])
                self.assertEqual(result.total, 1100)
                self.assertEqual(result.page_size, 25)

    def test_suppliers_load_beyond_the_database_row_limit(self) -> None:
        rows = [{"supplier_id": f"P{index:04}", "legal_name": "Empresa", "tax_id": "B12345678",
                 "iban": "ES1234", "city": "Madrid", "payment_terms_days": 30} for index in range(1050)]
        client = MagicMock()
        query = client.table.return_value.select.return_value.order.return_value
        query.range.return_value.execute.side_effect = [MagicMock(data=rows[:1000]), MagicMock(data=rows[1000:])]
        with patch("suppliers.repository.get_client", return_value=client):
            result = list_suppliers()
        self.assertEqual([supplier.supplier_id for supplier in result], [row["supplier_id"] for row in rows])
        self.assertEqual(query.range.call_args_list, [call(0, 999), call(1000, 1999)])
