import unittest
from unittest.mock import MagicMock, call, patch
from uuid import UUID

from suppliers.repository import list_suppliers
from usage.router import get_usage


class TableCollectionsTests(unittest.TestCase):
    def test_usage_loads_all_records_beyond_the_dashboard_and_database_page_limits(self) -> None:
        records = [{
            "id": str(UUID(int=index + 1)), "created_at": "2026-09-19T14:00:00Z",
            "provider": "openrouter", "model": "extraction", "operation": "extraction",
            "document_id": str(UUID(int=1)), "document_name": "invoice.pdf", "usage": [],
        } for index in range(1100)]
        client = MagicMock()
        client.rpc.return_value.execute.return_value.data = {
            "records": records[:25], "total": 1100, "page_size": 25, "daily": [],
            "summary": {"calls": 1100, "pages": 1100, "cost_usd": "4.4", "average_document_cost_usd": "4.4"},
        }
        query = client.table.return_value.select.return_value.order.return_value.order.return_value
        query.or_.return_value.limit.return_value.execute.side_effect = [MagicMock(data=records[25:1025]), MagicMock(data=records[1025:])]
        with patch("usage.router.get_client", return_value=client), patch("usage.router.get_redis") as redis:
            redis.return_value.__enter__.return_value.hvals.return_value = []
            result = get_usage()
        self.assertEqual([record.id for record in result.records], [record["id"] for record in records])
        self.assertEqual(query.or_.return_value.limit.call_args_list, [call(1000), call(75)])
        self.assertIn(f"id.lt.{records[24]['id']}", query.or_.call_args_list[0].args[0])
        self.assertIn(f"id.lt.{records[1024]['id']}", query.or_.call_args_list[1].args[0])
        self.assertNotIn("page_size", result.model_dump())

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
