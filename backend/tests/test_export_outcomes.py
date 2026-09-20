import json
import unittest
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from export_outcomes import Invoice, batch_outcomes, export, read_invoices


class ExportOutcomesTests(unittest.TestCase):
    def test_original_unicode_filename_and_saved_decision_are_preserved(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'informática.pdf'
            path.write_bytes(b'%PDF-example')
            invoice: Invoice = {'sha256': sha256(path.read_bytes()).hexdigest(), 'status': 'ready',
                                'payment_decision': {'classification': 'ESCALAR'}}
            self.assertEqual(batch_outcomes(Path(directory), 1, [invoice]),
                             [{'file_id': path.name, 'result': 'ESCALAR'}])
            for rows in ([], [invoice, invoice], [{**invoice, 'status': 'processing'}],
                         [{**invoice, 'payment_decision': None}]):
                with self.subTest(rows=rows), self.assertRaises(ValueError):
                    batch_outcomes(Path(directory), 1, rows)

    def test_batch_counts_are_required(self) -> None:
        with TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, '500 PDFs'):
            batch_outcomes(Path(directory), 500, [])

    def test_both_batches_are_validated_before_any_output_is_written(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'output'
            with patch('export_outcomes.read_invoices', return_value=[]), \
                 patch('export_outcomes.batch_outcomes', side_effect=[[], ValueError('Lote incompleto')]):
                with self.assertRaisesRegex(ValueError, 'Lote incompleto'):
                    export('http://app/api', root, output, 'password')
            self.assertFalse(output.exists())

    def test_writes_two_jsonl_files_with_only_the_contract_fields(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            batches = [[{'file_id': 'informática.pdf', 'result': 'PAGAR'}],
                       [{'file_id': 'e14.pdf', 'result': 'ESCALAR'}]]
            with patch('export_outcomes.read_invoices', return_value=[]), \
                 patch('export_outcomes.batch_outcomes', side_effect=batches):
                counts = export('http://app/api', root, root / 'output', 'password')
            self.assertEqual(counts, {'outcomes.jsonl': 1, 'outcomes_lote2.jsonl': 1})
            for name, expected in zip(counts, batches):
                text = (root / 'output' / name).read_text(encoding='utf-8')
                self.assertTrue(text.endswith('\n'))
                self.assertEqual([json.loads(line) for line in text.splitlines()], expected)

    def test_authenticates_before_reading_invoices(self) -> None:
        login_response = BytesIO(b'')
        invoices_response = BytesIO(b'[]')
        opener = MagicMock()
        opener.open.side_effect = [login_response, invoices_response]
        with patch('export_outcomes.build_opener', return_value=opener):
            self.assertEqual(read_invoices('http://app/api', 'secret'), [])
        login_request = opener.open.call_args_list[0].args[0]
        self.assertEqual(login_request.full_url, 'http://app/api/auth/login')
        self.assertEqual(json.loads(login_request.data), {'password': 'secret'})
        self.assertEqual(opener.open.call_args_list[1].args[0], 'http://app/api/invoices')
