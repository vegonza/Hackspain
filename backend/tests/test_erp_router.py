import unittest
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from erp.repository import read_entry, read_latest_snapshot
from erp.router import get_entry, get_snapshot, refresh_snapshot
from erp.warnings import ErpWarning


def entry_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        'id': str(uuid4()), 'entry_id': 'AS-00084', 'supplier_id': 'P002', 'tax_id': 'A41220987',
        'order_id': 'PO-2026-0084', 'status': 'PENDIENTE', 'date': '2026-03-21', 'amount': '6199.54',
        'raw_date': '21/03/2026', 'raw_amount': '6.199,54', 'warnings': [],
    }
    row.update(overrides)
    return row


def snapshot_row(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'id': str(uuid4()), 'fetched_at': '2026-09-19T12:47:00+00:00',
        'erp_version': '2.3.1', 'update_loaded': False, 'entry_count': len(entries), 'entries': entries,
    }


def database(payload: dict[str, Any] | None) -> MagicMock:
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = payload
    return client


class ErpSnapshotReadTests(unittest.TestCase):
    def test_without_a_saved_download_returns_none(self) -> None:
        with patch('erp.repository.get_client', return_value=database(None)):
            self.assertIsNone(read_latest_snapshot())

    def test_complete_snapshot_uses_one_rpc_without_client_side_row_limits(self) -> None:
        rows = [entry_row(entry_id=f'AS-{index:05}') for index in range(1200)]
        client = database(snapshot_row(rows))
        with patch('erp.repository.get_client', return_value=client):
            snapshot = read_latest_snapshot()
        assert snapshot is not None
        self.assertEqual(len(snapshot.entries), 1200)
        self.assertEqual(snapshot.entry_count, 1200)
        self.assertEqual(snapshot.entries[-1].entry_id, 'AS-01199')
        client.rpc.assert_called_once_with('get_erp_snapshot', {})
        client.table.assert_not_called()

    def test_preserves_exact_amounts_dates_and_parser_warnings(self) -> None:
        rows = [
            entry_row(amount='6199.540000000000001', warnings=['english_amount_format']),
            entry_row(tax_id='', date=None, amount=None, warnings=['missing_tax_id', 'missing_date']),
        ]
        with patch('erp.repository.get_client', return_value=database(snapshot_row(rows))):
            snapshot = read_latest_snapshot()
        assert snapshot is not None
        first, second = snapshot.entries
        self.assertEqual(first.amount, Decimal('6199.540000000000001'))
        self.assertEqual(first.date, date(2026, 3, 21))
        self.assertEqual(first.warnings, [ErpWarning.ENGLISH_AMOUNT_FORMAT])
        self.assertEqual(first.raw_amount, '6.199,54')
        self.assertEqual(first.model_dump(mode='json')['amount'], '6199.540000000000001')
        self.assertIsNone(second.amount)
        self.assertIsNone(second.date)
        self.assertEqual(second.tax_id, '')
        self.assertEqual(second.warnings, [ErpWarning.MISSING_TAX_ID, ErpWarning.MISSING_DATE])


class ErpEntryReadTests(unittest.TestCase):
    def test_entry_is_resolved_by_uuid_without_reading_the_latest_snapshot(self) -> None:
        document = {'id': str(uuid4()), 'name': 'factura.pdf'}
        row = entry_row(documents=[document])
        client = database(row)
        with patch('erp.repository.get_client', return_value=client):
            entry = read_entry(UUID(row['id']))
        assert entry is not None
        self.assertEqual(str(entry.id), row['id'])
        self.assertEqual(entry.model_dump(mode='json')['documents'], [document])
        client.rpc.assert_called_once_with('get_erp_entry', {'p_entry_id': row['id']})
        client.table.assert_not_called()

    def test_missing_entry_returns_none(self) -> None:
        with patch('erp.repository.get_client', return_value=database(None)):
            self.assertIsNone(read_entry(uuid4()))

    def test_entry_without_linked_documents_keeps_an_empty_list(self) -> None:
        row = entry_row(documents=[])
        with patch('erp.repository.get_client', return_value=database(row)):
            entry = read_entry(UUID(row['id']))
        assert entry is not None
        self.assertEqual(entry.documents, [])


class ErpRouteTests(unittest.TestCase):
    def test_snapshot_route_returns_the_saved_snapshot(self) -> None:
        with patch('erp.router.read_latest_snapshot') as read:
            self.assertIs(get_snapshot(), read.return_value)
            read.assert_called_once_with()

    def test_entry_route_passes_its_uuid(self) -> None:
        entry_id = uuid4()
        with patch('erp.router.read_entry') as read:
            self.assertIs(get_entry(entry_id), read.return_value)
            read.assert_called_once_with(entry_id)


class ErpRefreshTests(unittest.TestCase):
    def test_refresh_waits_for_the_validated_snapshot_to_be_saved(self) -> None:
        with patch('erp.router.sync_erp_snapshot', return_value=uuid4()) as sync:
            response = refresh_snapshot()
        sync.assert_called_once_with()
        self.assertEqual(response.status_code, 204)

    def test_download_failure_is_not_reported_as_success(self) -> None:
        with patch('erp.router.sync_erp_snapshot', side_effect=RuntimeError('ERP unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'ERP unavailable'):
                refresh_snapshot()
