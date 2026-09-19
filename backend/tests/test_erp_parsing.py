import unittest
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree
from unittest.mock import patch

from erp.parsing import parse_amount, parse_date, parse_entry_xml
from erp.warnings import ErpWarning


class ErpParsingTests(unittest.TestCase):
    def test_spanish_amounts_keep_precision(self) -> None:
        for raw, expected in (
            ("12.874,40", "12874.40"), ("524,98", "524.98"),
            ("-1.234,56", "-1234.56"), ("+0,00", "0.00"),
            ("12345678901234567890,12", "12345678901234567890.12"),
            ("1.234.567", "1234567"), ("42", "42"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(parse_amount(raw), (Decimal(expected), None))

    def test_english_amounts_are_not_multiplied_by_100(self) -> None:
        for raw, expected in (("1234.56", "1234.56"), ("1,234.56", "1234.56"), ("1,234,567", "1234567")):
            with self.subTest(raw=raw):
                self.assertEqual(parse_amount(raw), (Decimal(expected), ErpWarning.ENGLISH_AMOUNT_FORMAT))

    def test_spanish_format_takes_precedence_without_rounding(self) -> None:
        for raw, expected in (
            ("1.234", "1234"), ("1,234", "1.234"),
            ("-1.234", "-1234"), ("-1,234", "-1.234"),
            ("1.234,56789", "1234.56789"), ("0,12345678901234567890", "0.12345678901234567890"),
        ):
            with self.subTest(raw=raw):
                value, warning = parse_amount(raw)
                self.assertEqual(value, Decimal(expected))
                self.assertIsNone(warning)
        self.assertEqual(parse_amount("1234.567"), (Decimal("1234.567"), ErpWarning.ENGLISH_AMOUNT_FORMAT))

    def test_space_thousands_separators_preserve_precision_and_raw_value(self) -> None:
        for separator in (" ", "\u00a0", "\u202f"):
            raw = f"-1{separator}234{separator}567,8901"
            with self.subTest(separator=separator):
                self.assertEqual(parse_amount(raw), (Decimal("-1234567.8901"), None))
                entry = parse_entry_xml(f'<asiento><importe>{raw}</importe></asiento>'.encode())
                self.assertEqual(entry.raw_amount, raw)
                self.assertEqual(entry.amount, Decimal("-1234567.8901"))
        self.assertEqual(parse_amount("1 234"), (Decimal("1234"), None))
        for raw in ("1 2", "12 34,56", "1234 567", "1  234", "1\t234", "1\n234", "1.234 567", "1 234,5 6"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_amount(raw), (None, ErpWarning.INVALID_AMOUNT))

    def test_malformed_amounts_are_rejected(self) -> None:
        for raw in ("12,34,56", "1..2", "12.34,56", "1,234,56.78", "NaN", "Infinity", "IVA 21%: 295,97", "1 2", "1,", "1e3"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_amount(raw), (None, ErpWarning.INVALID_AMOUNT))
        self.assertEqual(parse_amount(" "), (None, ErpWarning.MISSING_AMOUNT))

    def test_dates_and_impossible_dates(self) -> None:
        self.assertEqual(parse_date("03/04/2026"), (date(2026, 4, 3), None))
        self.assertEqual(parse_date("29/02/2024"), (date(2024, 2, 29), None))
        self.assertEqual(parse_date("2026-04-03"), (date(2026, 4, 3), ErpWarning.ISO_DATE_FORMAT))
        for raw in ("31/02/2026", "29/02/2025", "unknown"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_date(raw), (None, ErpWarning.INVALID_DATE))
        self.assertEqual(parse_date(""), (None, ErpWarning.MISSING_DATE))

    def test_spanish_dates_accept_unpadded_day_and_month(self) -> None:
        for raw in ("1/2/2026", "01/2/2026", "1/02/2026"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_date(raw), (date(2026, 2, 1), None))
        for raw in ("0/2/2026", "1/0/2026", "29/2/2026", "31/4/2026", "001/2/2026"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_date(raw), (None, ErpWarning.INVALID_DATE))

    def test_xml_encoding_original_values_and_json_contract(self) -> None:
        xml = '''<?xml version="1.0" encoding="ISO-8859-1"?>
        <asiento><id>AS-1</id><proveedor>Peña</proveedor><nif>B12345678</nif>
        <pedido>PO-1</pedido><estado>PENDIENTE</estado>
        <fecha> 12/01/2026 </fecha><importe> 1.234,56 </importe></asiento>'''
        entry = parse_entry_xml(xml.encode('iso-8859-1'))
        self.assertEqual(entry.supplier_id, 'Peña')
        self.assertEqual(entry.raw_date, ' 12/01/2026 ')
        self.assertEqual(entry.raw_amount, ' 1.234,56 ')
        payload = entry.model_dump(mode='json')
        self.assertEqual(payload['date'], '2026-01-12')
        self.assertEqual(payload['amount'], '1234.56')
        self.assertEqual(payload['warnings'], [])

    def test_bad_data_is_preserved_with_serializable_warnings(self) -> None:
        entry = parse_entry_xml(b'<asiento><id>AS-1</id><proveedor>P?</proveedor><nif/><pedido>PO-1</pedido><estado>ANULADA</estado><fecha>31/02/2026</fecha><importe>N/A</importe></asiento>')
        self.assertIsNone(entry.date)
        self.assertIsNone(entry.amount)
        self.assertEqual(entry.status, 'ANULADA')
        self.assertEqual(entry.model_dump(mode='json')['warnings'], [
            'invalid_date', 'invalid_amount', 'missing_tax_id', 'unknown_status', 'possible_character_loss',
        ])

    def test_empty_entry_reports_each_missing_field(self) -> None:
        entry = parse_entry_xml(b'<asiento/>')
        self.assertEqual(set(entry.warnings), {
            ErpWarning.MISSING_ENTRY_ID, ErpWarning.MISSING_SUPPLIER_ID, ErpWarning.MISSING_TAX_ID,
            ErpWarning.MISSING_ORDER_ID, ErpWarning.MISSING_STATUS, ErpWarning.MISSING_DATE,
            ErpWarning.MISSING_AMOUNT,
        })

    def test_broken_xml_fails_instead_of_producing_an_empty_entry(self) -> None:
        with self.assertRaises(ElementTree.ParseError):
            parse_entry_xml(b'<asiento>')
        with self.assertRaises(ValueError):
            parse_entry_xml(b'<error><codigo>SES-401</codigo></error>')

    def test_date_range_warns_without_discarding_dates(self) -> None:
        for raw, expected, outside in (
            ("31/12/1899", date(1899, 12, 31), True),
            ("01/01/1900", date(1900, 1, 1), False),
            ("19/09/2026", date(2026, 9, 19), False),
            ("20/09/2026", date(2026, 9, 20), True),
        ):
            with self.subTest(raw=raw), patch('erp.parsing.date') as calendar:
                calendar.today.return_value = date(2026, 9, 19)
                entry = parse_entry_xml(f'<asiento><fecha>{raw}</fecha></asiento>'.encode())
                self.assertEqual(entry.date, expected)
                self.assertEqual(entry.raw_date, raw)
                self.assertEqual(ErpWarning.DATE_OUT_OF_RANGE in entry.warnings, outside)

    def test_date_range_keeps_other_warnings(self) -> None:
        with patch('erp.parsing.date') as calendar:
            calendar.today.return_value = date(2026, 9, 19)
            entry = parse_entry_xml(b'<asiento><fecha>2026-09-20</fecha></asiento>')
        self.assertIn(ErpWarning.ISO_DATE_FORMAT, entry.warnings)
        self.assertIn(ErpWarning.DATE_OUT_OF_RANGE, entry.warnings)
        invalid = parse_entry_xml(b'<asiento><fecha>31/02/2026</fecha></asiento>')
        self.assertIn(ErpWarning.INVALID_DATE, invalid.warnings)
        self.assertNotIn(ErpWarning.DATE_OUT_OF_RANGE, invalid.warnings)
