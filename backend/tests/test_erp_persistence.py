import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from erp.errors import ErpProtocolError
from erp.models import ErpEntry, ErpSnapshot, ErpStatus
from erp.repository import save_snapshot
from erp.service import sync_erp_snapshot
from erp.warnings import ErpWarning


class ErpPersistenceTests(unittest.TestCase):
    def test_rpc_keeps_precision_duplicates_originals_and_warnings(self) -> None:
        state = ErpStatus(version='2.3.1', uptime_seconds=100, entry_count=2, update_loaded=True)
        entry = ErpEntry(entry_id='AS-1', supplier_id='P1', tax_id='', order_id='PO1',
                         status='PENDIENTE', raw_date='bad date', raw_amount='1.234,56789',
                         amount=Decimal('1234.56789'), warnings=[ErpWarning.INVALID_DATE])
        snapshot = ErpSnapshot(fetched_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
                               status_before=state, status_after=state, entries=[entry, entry])
        client = MagicMock()
        identifier = uuid4()
        client.rpc.return_value.execute.return_value.data = str(identifier)
        with patch('erp.repository.get_client', return_value=client):
            self.assertEqual(save_snapshot(snapshot), identifier)
        client.rpc.assert_called_once_with('save_erp_snapshot', {
            'p_fetched_at': '2026-09-19T00:00:00+00:00', 'p_erp_version': '2.3.1',
            'p_update_loaded': True, 'p_entries': [entry.model_dump(mode='json')] * 2,
        })
        payload = client.rpc.call_args.args[1]['p_entries'][0]
        self.assertEqual(payload['amount'], '1234.56789')
        self.assertIsNone(payload['date'])
        self.assertEqual(payload['raw_date'], 'bad date')
        self.assertEqual(payload['warnings'], ['invalid_date'])

    def test_sync_saves_download_after_closing_erp_client(self) -> None:
        with patch('erp.service.ErpClient.from_env') as factory, patch('erp.service.save_snapshot') as save:
            client = factory.return_value.__enter__.return_value
            identifier = uuid4()

            def persist(snapshot: ErpSnapshot) -> object:
                factory.return_value.__exit__.assert_called_once()
                self.assertIs(snapshot, client.get_snapshot.return_value)
                return identifier

            save.side_effect = persist
            self.assertEqual(sync_erp_snapshot(), identifier)
            client.get_snapshot.assert_called_once_with()
            save.assert_called_once_with(client.get_snapshot.return_value)

    def test_failed_download_does_not_write_to_database(self) -> None:
        with patch('erp.service.ErpClient.from_env') as factory, patch('erp.service.save_snapshot') as save:
            factory.return_value.__enter__.return_value.get_snapshot.side_effect = ErpProtocolError('incomplete')
            with self.assertRaises(ErpProtocolError):
                sync_erp_snapshot()
            save.assert_not_called()
            factory.return_value.__exit__.assert_called_once()

    def test_database_failure_is_propagated_without_redownloading(self) -> None:
        with patch('erp.service.ErpClient.from_env') as factory, patch('erp.service.save_snapshot') as save:
            save.side_effect = RuntimeError('database unavailable')
            with self.assertRaisesRegex(RuntimeError, 'database unavailable'):
                sync_erp_snapshot()
            factory.return_value.__enter__.return_value.get_snapshot.assert_called_once_with()
            save.assert_called_once()
