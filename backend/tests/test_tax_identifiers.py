import unittest
from datetime import date
from decimal import Decimal

from erp.models import ErpEntry
from orders.models import OrderInput
from shared.identifiers import compact_identifier, normalize_tax_id, order_key
from suppliers.models import SupplierInput


class TaxIdentifierTests(unittest.TestCase):
    def test_formatting_preserves_letters_and_leading_zeroes(self) -> None:
        for original, expected in (
            ('12.345.678/0001-95', '12345678000195'),
            (' de 812345678 ', 'DE812345678'),
            ('00.abC/0001-95', '00ABC000195'),
            ('5010401075570', '5010401075570'),
            ('B?123', 'B?123'),
        ):
            with self.subTest(original=original):
                self.assertEqual(normalize_tax_id(original), expected)
        self.assertEqual(compact_identifier('ES00 12-34'), 'ES0012-34')
        self.assertEqual(order_key(' f/001-02 '), 'F/001-02')

    def test_master_data_and_erp_share_normalization(self) -> None:
        tax_id = '12.345.678/0001-95'
        supplier = SupplierInput(legal_name='Proveedor', tax_id=tax_id, iban='BR97 00',
                                 city='São Paulo', payment_terms_days=30)
        order = OrderInput(supplier_id='P014', tax_id=tax_id, amount=Decimal('1'),
                           status='ABIERTO', date=date(2026, 9, 1))
        entry = ErpEntry(entry_id='AS1', supplier_id='P014', tax_id=tax_id,
                         order_id='PO1', status='PENDIENTE', raw_date='', raw_amount='')
        for record in (supplier, order, entry):
            self.assertEqual(record.tax_id, '12345678000195')
