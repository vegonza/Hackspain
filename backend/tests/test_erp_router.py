import unittest
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from erp.repository import read_latest_snapshot
from erp.router import get_snapshot
from erp.warnings import ErpWarning


def snapshot_row(identifier: str) -> dict[str, Any]:
    return {'id': identifier, 'fetched_at': '2026-09-19T12:47:00+00:00', 'erp_version': '2.3.1', 'update_loaded': False, 'entry_count': 2}


def entry_row(snapshot_id: str, entry_id: str, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        'id': str(uuid4()), 'snapshot_id': snapshot_id, 'entry_id': entry_id, 'supplier_id': 'P002', 'tax_id': 'A41220987',
        'order_id': 'PO-2026-0084', 'status': 'PENDIENTE', 'date': '2026-03-21', 'amount': 6199.54,
        'raw_date': '21/03/2026', 'raw_amount': '6.199,54', 'warnings': [],
    }
    row.update(overrides)
    return row


def document_row(entry_id: str | None, name: str) -> dict[str, Any]:
    return {'id': str(uuid4()), 'name': name, 'erp_entry_id': entry_id}


def database(snapshots: list[dict[str, Any]], entries: list[dict[str, Any]], documents: list[dict[str, Any]] | None = None) -> tuple[MagicMock, dict[str, MagicMock]]:
    tables = {'erp_snapshots': MagicMock(), 'erp_entries': MagicMock(), 'documents': MagicMock()}
    tables['erp_snapshots'].select.return_value.order.return_value.order.return_value.limit.return_value.execute.return_value.data = snapshots
    tables['erp_entries'].select.return_value.eq.return_value.order.return_value.execute.return_value.data = entries
    tables['documents'].select.return_value.eq.return_value.is_.return_value.order.return_value.execute.return_value.data = documents or []
    client = MagicMock()
    client.table.side_effect = lambda name: tables[name]
    return client, tables


class ErpSnapshotReadTests(unittest.TestCase):
    def test_without_a_saved_download_nothing_is_returned_and_no_entries_are_read(self) -> None:
        client, tables = database([], [])
        with patch('erp.repository.get_client', return_value=client):
            self.assertIsNone(read_latest_snapshot())
        tables['erp_entries'].select.assert_not_called()
        tables['documents'].select.assert_not_called()

    def test_reads_the_newest_download_and_only_its_entries_in_a_stable_order(self) -> None:
        identifier = str(uuid4())
        client, tables = database([snapshot_row(identifier)], [entry_row(identifier, 'AS-00084')])
        with patch('erp.repository.get_client', return_value=client):
            read_latest_snapshot()
        newest = tables['erp_snapshots'].select.return_value
        tables['erp_snapshots'].select.assert_called_once_with('*')
        newest.order.assert_called_once_with('fetched_at', desc=True)
        newest.order.return_value.order.assert_called_once_with('id', desc=True)
        newest.order.return_value.order.return_value.limit.assert_called_once_with(1)
        tables['erp_entries'].select.return_value.eq.assert_called_once_with('snapshot_id', identifier)
        tables['erp_entries'].select.return_value.eq.return_value.order.assert_called_once_with('entry_id')

    def test_entries_keep_their_amounts_dates_and_warnings(self) -> None:
        identifier = str(uuid4())
        rows = [
            entry_row(identifier, 'AS-00084', warnings=['english_amount_format']),
            entry_row(identifier, 'AS-77001', tax_id='', date=None, amount=None, warnings=['missing_tax_id', 'missing_date']),
        ]
        client, _ = database([snapshot_row(identifier)], rows)
        with patch('erp.repository.get_client', return_value=client):
            snapshot = read_latest_snapshot()
        assert snapshot is not None
        first, second = snapshot.entries
        self.assertEqual(snapshot.entry_count, 2)
        self.assertEqual(first.amount, Decimal('6199.54'))
        self.assertEqual(first.date, date(2026, 3, 21))
        self.assertEqual(first.warnings, [ErpWarning.ENGLISH_AMOUNT_FORMAT])
        self.assertEqual(first.raw_amount, '6.199,54')
        self.assertIsNone(second.amount)
        self.assertIsNone(second.date)
        self.assertEqual(second.tax_id, '')
        self.assertEqual(second.warnings, [ErpWarning.MISSING_TAX_ID, ErpWarning.MISSING_DATE])

    def test_amounts_reach_the_client_as_exact_decimal_text(self) -> None:
        identifier = str(uuid4())
        client, _ = database([snapshot_row(identifier)], [entry_row(identifier, 'AS-00084', amount=6199.54)])
        with patch('erp.repository.get_client', return_value=client):
            snapshot = read_latest_snapshot()
        assert snapshot is not None
        payload = snapshot.model_dump(mode='json')
        self.assertEqual(payload['entries'][0]['amount'], '6199.54')
        self.assertEqual(payload['erp_version'], '2.3.1')
        self.assertFalse(payload['update_loaded'])


class ErpLinkedDocumentsTests(unittest.TestCase):
    def read(self, entries: list[dict[str, Any]], documents: list[dict[str, Any]], identifier: str) -> Any:
        client, tables = database([snapshot_row(identifier)], entries, documents)
        with patch('erp.repository.get_client', return_value=client):
            snapshot = read_latest_snapshot()
        self.tables = tables
        assert snapshot is not None
        return snapshot

    def test_each_entry_lists_the_invoices_linked_to_it_in_order(self) -> None:
        identifier = str(uuid4())
        first, second = entry_row(identifier, 'AS-00001'), entry_row(identifier, 'AS-00002')
        documents = [document_row(first['id'], 'a.pdf'), document_row(second['id'], 'b.pdf'), document_row(first['id'], 'c.pdf')]
        snapshot = self.read([first, second], documents, identifier)
        self.assertEqual([document.name for document in snapshot.entries[0].documents], ['a.pdf', 'c.pdf'])
        self.assertEqual([document.name for document in snapshot.entries[1].documents], ['b.pdf'])

    def test_entries_without_invoices_have_an_empty_list(self) -> None:
        identifier = str(uuid4())
        snapshot = self.read([entry_row(identifier, 'AS-00001')], [], identifier)
        self.assertEqual(snapshot.entries[0].documents, [])

    def test_invoices_without_a_linked_entry_are_ignored(self) -> None:
        identifier = str(uuid4())
        entry = entry_row(identifier, 'AS-00001')
        snapshot = self.read([entry], [document_row(None, 'unmatched.pdf'), document_row(entry['id'], 'matched.pdf')], identifier)
        self.assertEqual([document.name for document in snapshot.entries[0].documents], ['matched.pdf'])

    def test_only_active_invoices_of_the_same_download_are_read(self) -> None:
        identifier = str(uuid4())
        self.read([entry_row(identifier, 'AS-00001')], [], identifier)
        query = self.tables['documents'].select
        query.assert_called_once_with('id,name,erp_entry_id')
        query.return_value.eq.assert_called_once_with('erp_snapshot_id', identifier)
        query.return_value.eq.return_value.is_.assert_called_once_with('deleted_at', 'null')
        query.return_value.eq.return_value.is_.return_value.order.assert_called_once_with('name')

    def test_linked_invoices_reach_the_client(self) -> None:
        identifier = str(uuid4())
        entry = entry_row(identifier, 'AS-00001')
        document = document_row(entry['id'], 'a.pdf')
        payload = self.read([entry], [document], identifier).model_dump(mode='json')
        self.assertEqual(payload['entries'][0]['documents'], [{'id': document['id'], 'name': 'a.pdf'}])


class ErpSnapshotRouteTests(unittest.TestCase):
    def test_route_returns_what_the_repository_reads(self) -> None:
        with patch('erp.router.read_latest_snapshot') as read:
            self.assertIs(get_snapshot(), read.return_value)
            read.assert_called_once_with()

    def test_route_returns_nothing_before_the_first_download(self) -> None:
        with patch('erp.router.read_latest_snapshot', return_value=None):
            self.assertIsNone(get_snapshot())
