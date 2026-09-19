import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from postgrest.exceptions import APIError

from suppliers.models import Supplier
from suppliers.repository import create_supplier, update_supplier


class SuppliersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.supplier = Supplier(supplier_id='P001', legal_name=' Empresa S.L. ', tax_id=' b12345678 ',
                                 iban='es12 3456 7890', city='Valencia', payment_terms_days=60)

    def test_save_normalizes_supplier_identifiers(self) -> None:
        client = MagicMock()
        client.table.return_value.insert.return_value.execute.return_value.data = [self.supplier.model_dump()]
        with patch('suppliers.repository.get_client', return_value=client):
            result = create_supplier(self.supplier)
        self.assertEqual(result.iban, 'ES1234567890')
        self.assertEqual(result.tax_id, 'B12345678')
        self.assertEqual(result.legal_name, 'Empresa S.L.')
        client.table.return_value.insert.assert_called_once_with(self.supplier.model_dump())

    def test_duplicate_supplier_returns_conflict(self) -> None:
        client = MagicMock()
        client.table.return_value.insert.return_value.execute.side_effect = APIError({
            'code': '23505', 'message': 'duplicate supplier', 'details': '', 'hint': '',
        })
        with patch('suppliers.repository.get_client', return_value=client):
            with self.assertRaises(HTTPException) as caught:
                create_supplier(self.supplier)
        self.assertEqual(caught.exception.status_code, 409)

    def test_missing_supplier_cannot_be_updated(self) -> None:
        client = MagicMock()
        client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
        with patch('suppliers.repository.get_client', return_value=client):
            with self.assertRaises(HTTPException) as caught:
                update_supplier('P001', self.supplier)
        self.assertEqual(caught.exception.status_code, 404)
