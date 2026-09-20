from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime, timezone

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.pdfgen.canvas import Canvas

from extractor.metadata import ExtractionMetadata
from extractor.pages import render_pages
from extractor.verifactu import detect_verifactu, parse_verifactu
from invoices.repository import InvoiceDetails
from invoices.router import invoice_detail

URL = 'https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?nif=B12959755&numserie=TEST%2F1&fecha=20-09-2026&importe=121.00'


def pdf_pages(urls: list[str | None]) -> list[bytes]:
    output = BytesIO()
    canvas = Canvas(output)
    for url in urls:
        canvas.drawString(50, 700, 'Factura de prueba')
        if url is not None:
            code = QrCodeWidget(url, barWidth=110, barHeight=110)
            drawing = Drawing(110, 110)
            drawing.add(code)
            renderPDF.draw(drawing, canvas, 400, 680)
        canvas.showPage()
    canvas.save()
    return render_pages(output.getvalue())


class IncomingVerifactuTests(TestCase):
    def test_accepts_only_official_verifactu_endpoints_and_complete_parameters(self) -> None:
        self.assertEqual(parse_verifactu(URL, 2).environment, 'test')
        self.assertEqual(parse_verifactu(URL.replace('prewww2.aeat.es', 'www2.agenciatributaria.gob.es'), 1).environment, 'production')
        invalid = [
            URL.replace('ValidarQR?', 'ValidarQRNoVerifactu?'),
            URL.replace('prewww2.aeat.es', 'prewww2.aeat.es.evil.example'),
            URL.replace('prewww2.aeat.es', 'user@prewww2.aeat.es'),
            URL.replace('https:', 'http:'), URL + '#fragment', URL + '&importe=121',
            URL.replace('&importe=121.00', ''), URL.replace('121.00', '121,00'),
            URL.replace('20-09-2026', '31-02-2026'), URL.replace('TEST%2F1', ''),
            URL.replace('prewww2.aeat.es', '[invalid'), 'Plantilla',
        ]
        for value in invalid:
            with self.subTest(value=value):
                self.assertIsNone(parse_verifactu(value, 1))

    def test_decodes_rendered_pdf_and_finds_code_on_later_page(self) -> None:
        result = detect_verifactu(pdf_pages([None, URL, URL]))
        self.assertEqual(result.url, URL)
        self.assertEqual(result.page, 2)

    def test_no_matching_or_ambiguous_codes_are_null(self) -> None:
        self.assertIsNone(detect_verifactu(pdf_pages([None, 'https://example.com'])))
        self.assertIsNone(detect_verifactu(pdf_pages([URL, URL.replace('TEST%2F1', 'TEST%2F2')])))
        self.assertIsNone(ExtractionMetadata().verifactu)

    def test_detail_exposes_saved_qr_without_changing_extracted_invoice(self) -> None:
        from extractor.categories import CategorizedInvoiceExtraction
        extraction = {key: '' for key in ('invoice_number', 'supplier_name', 'supplier_nif', 'iban', 'invoice_date', 'purchase_order', 'currency', 'tax_base', 'vat_rate', 'vat_amount', 'total')}
        extraction.update(line_items=[], notes=[], uncertainties=[])
        features = CategorizedInvoiceExtraction.model_validate(extraction).model_dump_json().encode()
        document = InvoiceDetails(id=uuid4(), name='test.pdf', sha256='a' * 64,
                                  created_at=datetime.now(timezone.utc), result_path='features.json')
        qr = parse_verifactu(URL, 1)
        metadata = ExtractionMetadata(verifactu=qr).model_dump_json().encode()
        with patch('invoices.router.download_file', side_effect=[features, b'text', metadata]):
            result = invoice_detail(document)
        self.assertEqual(result.verifactu, qr)
        self.assertEqual(result.identifier_trace.identifier_corrections, [])
