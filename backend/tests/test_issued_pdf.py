import subprocess
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from PIL import Image

from issued.models import Line, totals
from issued.pdf import render_invoice
from tests.test_issued_invoices import sample_invoice


class IssuedPdfTests(TestCase):
    def test_bank_logo_and_full_bleed_header_are_in_the_export(self) -> None:
        invoice = sample_invoice('issued')
        invoice.company.name = 'Banco Miralmar S.A.'
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'invoice.pdf'
            path.write_bytes(render_invoice(invoice))
            result = subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-scale-to', '900', '-png', str(path)],
                                    check=True, capture_output=True)
            image = Image.open(BytesIO(result.stdout)).convert('RGB')
            self.assertEqual(image.getpixel((0, 0)), (244, 247, 249))
            self.assertEqual(image.getpixel((image.width - 2, 0)), (244, 247, 249))
            logo = image.crop((40, 15, 85, 65))
            self.assertTrue(any(g > 120 and b > 120 and r < 70 for r, g, b in (logo.getpixel((x, y)) for y in range(logo.height) for x in range(logo.width))))
            text = subprocess.check_output(['pdftotext', str(path), '-'], text=True)
            for value in ['Banco Miralmar S.A.', 'Fecha de emisión', 'Vencimiento', 'Total con IVA', '242,00 €']:
                self.assertIn(value, text)

    def test_long_invoices_keep_every_line_and_repeat_the_table_heading(self) -> None:
        invoice = sample_invoice('issued')
        invoice.company.name = 'Banco Miralmar S.A.'
        invoice.items = [Line(description=f'CONCEPTO-{index:03d} ' + 'Servicio de consultoría administrativa. ' * 5,
                              quantity='1', unit_price='100', tax_rate='21') for index in range(45)]
        invoice.base_amount, invoice.tax_amount, invoice.total_amount = totals(invoice.items)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'long.pdf'
            path.write_bytes(render_invoice(invoice))
            text = subprocess.check_output(['pdftotext', str(path), '-'], text=True)
            pages = [page for page in text.split('\f') if page.strip()]
            self.assertGreater(len(pages), 1)
            for index in range(45):
                self.assertEqual(text.count(f'CONCEPTO-{index:03d} '), 1)
            for page in pages:
                if 'CONCEPTO-' in page:
                    self.assertEqual(page.count('PRECIO SIN IVA'), 1)
                self.assertIn('Gracias por confiar en nosotros', page)
            self.assertIn('5.445,00 €', text)
