import unittest
from unittest.mock import Mock

from erp.client import ErpClient
from erp.errors import ErpProtocolError
from erp.models import ErpEntry, ErpPage, ErpStatus
from erp.snapshots import download_snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = Mock(spec=ErpClient)
        self.status = ErpStatus(version='2.3.1', uptime_seconds=100, entry_count=3, update_loaded=False)
        self.entry = ErpEntry(entry_id='AS-1', supplier_id='P1', tax_id='B1', order_id='PO1',
                              status='PENDIENTE', raw_date='12/01/2026', raw_amount='1,00')
        self.first = ErpPage(number=1, total_pages=2, total_entries=3, page_size=2,
                             entries=[self.entry, self.entry])
        self.last = ErpPage(number=2, total_pages=2, total_entries=3, page_size=2, entries=[self.entry])
        self.client.get_status.side_effect = [self.status, self.status.model_copy(update={'uptime_seconds': 102})]
        self.client.get_page.side_effect = [self.first, self.last]

    def test_complete_snapshot_preserves_duplicates(self) -> None:
        snapshot = download_snapshot(self.client)
        self.assertEqual(len(snapshot.entries), 3)
        self.assertEqual([call.args[0] for call in self.client.get_page.call_args_list], [1, 2])
        self.assertEqual(self.client.get_status.call_count, 2)
        self.assertIsNotNone(snapshot.fetched_at.tzinfo)
        self.assertEqual(snapshot.status_after.version, '2.3.1')

    def test_short_page_is_rejected(self) -> None:
        self.client.get_page.side_effect = [self.first, self.last.model_copy(update={'entries': []})]
        with self.assertRaises(ErpProtocolError):
            download_snapshot(self.client)

    def test_changing_pagination_is_rejected(self) -> None:
        self.client.get_page.side_effect = [self.first, self.last.model_copy(update={'total_entries': 4})]
        with self.assertRaises(ErpProtocolError):
            download_snapshot(self.client)

    def test_source_state_changes_are_rejected(self) -> None:
        for change in ({'entry_count': 4}, {'update_loaded': True}, {'version': '2.4'}, {'uptime_seconds': 0}):
            with self.subTest(change=change):
                self.client.get_status.side_effect = [self.status, self.status.model_copy(update=change)]
                self.client.get_page.side_effect = [self.first, self.last]
                with self.assertRaises(ErpProtocolError):
                    download_snapshot(self.client)

    def test_source_total_must_match_pages(self) -> None:
        self.client.get_status.side_effect = [self.status.model_copy(update={'entry_count': 4})]
        with self.assertRaises(ErpProtocolError):
            download_snapshot(self.client)

    def test_empty_snapshot_is_not_accepted(self) -> None:
        self.client.get_status.side_effect = [self.status.model_copy(update={'entry_count': 0})]
        self.client.get_page.side_effect = [ErpPage(number=1, total_pages=1, total_entries=0, page_size=20, entries=[])]
        with self.assertRaises(ErpProtocolError):
            download_snapshot(self.client)
