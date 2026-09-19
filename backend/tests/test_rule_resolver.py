import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

from orders.models import Order
from rules.resolver import claim_order, resolve_references
from shared.identifiers import compact_identifier, order_key


class RuleResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.order = Order(order_id=' po-0001 ', supplier_id='P1', tax_id=None, amount=Decimal('121'),
                           status='ABIERTO', date=date(2026, 1, 1))

    def test_normalization_preserves_evidence_relevant_characters(self) -> None:
        self.assertEqual(order_key('\u00a0po-0001\u202f'), 'PO-0001')
        self.assertNotEqual(order_key('PO-OOO1'), order_key('PO-0001'))
        self.assertNotEqual(order_key('PO 0001'), order_key('PO-0001'))
        self.assertEqual(compact_identifier(' es00\u00a01234 '), 'ES001234')
        self.assertEqual(self.order.order_id, 'PO-0001')

    @patch('rules.resolver.get_client')
    def test_database_lookup_uses_document_and_normalized_key(self, client: MagicMock) -> None:
        client.return_value.rpc.return_value.execute.return_value = SimpleNamespace(data={
            'order': None, 'supplier': None, 'order_ambiguous': False, 'entries': [],
        })
        document_id = UUID('00000000-0000-0000-0000-000000000001')
        resolve_references(document_id, ' po-0001 ')
        client.return_value.rpc.assert_called_once_with('get_rule_references', {
            'p_document_id': str(document_id), 'p_order_key': 'PO-0001',
        })

    @patch('rules.resolver.get_client')
    def test_claim_returns_owner_or_missing_order(self, client: MagicMock) -> None:
        document_id = UUID('00000000-0000-0000-0000-000000000001')
        other_id = UUID('00000000-0000-0000-0000-000000000002')
        for owner in (document_id, other_id, None):
            with self.subTest(owner=owner):
                client.return_value.rpc.return_value.execute.return_value.data = str(owner) if owner is not None else None
                self.assertEqual(claim_order(document_id, ' po-0001 '), owner)
        client.return_value.rpc.assert_called_with('claim_invoice_order', {
            'p_document_id': str(document_id), 'p_order_key': 'PO-0001',
        })
