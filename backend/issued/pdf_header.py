from base64 import b64decode
from datetime import date
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, Paragraph
from svglib.svglib import svg2rlg

from issued.pdf_labels import LABELS

MARGIN = 14 * mm
LOGO_SIZE = 36
QR_SIZE = 32 * mm
QR_PADDING = 2 * mm
BRAND = colors.HexColor('#214c70')


class InvoiceHeader(Flowable):
    def __init__(self, company: str, number: str, issued: date, qr_code: str | None) -> None:
        super().__init__()
        self.width = A4[0] - 2 * MARGIN
        self.height = QR_SIZE + 2 * QR_PADDING + 24 + 18 + 21 if qr_code is not None else 126
        self.company = company
        self.number = number
        self.issued = issued
        self.qr_code = qr_code

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#f4f7f9'))
        canvas.rect(-MARGIN, 0, A4[0], self.height, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor('#dce2e6'))
        canvas.setLineWidth(.5)
        canvas.line(-MARGIN, 0, self.width + MARGIN, 0)

        title_x = 0
        if self.company.casefold() == 'banco miralmar s.a.':
            logo = svg2rlg(Path(__file__).with_name('assets') / 'banco-miralmar.svg')
            logo.scale(LOGO_SIZE / logo.width, LOGO_SIZE / logo.height)
            renderPDF.draw(logo, canvas, 0, self.height - 18 - LOGO_SIZE)
            title_x = LOGO_SIZE + 9
        title = Paragraph(escape(self.company), ParagraphStyle(
            'CompanyTitle', fontName='InvoiceSansBold', fontSize=18, leading=22, textColor=BRAND,
        ))
        title_width = self.width - title_x - (QR_SIZE + 2 * QR_PADDING + 18 if self.qr_code is not None else 0)
        _, title_height = title.wrap(title_width, self.height)
        title.drawOn(canvas, title_x, self.height - 18 - max(LOGO_SIZE, title_height) / 2 - title_height / 2)

        canvas.setFillColor(BRAND)
        canvas.setFont('InvoiceSansBold', 8.25)
        canvas.drawString(0, self.height - 18 - LOGO_SIZE - 29, f"{LABELS['invoice']} {self.number}")
        canvas.setFillColor(colors.HexColor('#66726e'))
        canvas.setFont('InvoiceSans', 9.75)
        canvas.drawString(0, self.height - 18 - LOGO_SIZE - 44, f'{self.issued:%d/%m/%Y}')

        if self.qr_code is not None:
            card_width = QR_SIZE + 2 * QR_PADDING
            card_height = QR_SIZE + 2 * QR_PADDING + 24
            left = self.width - card_width
            bottom = self.height - 18 - card_height
            canvas.setFillColor(colors.white)
            canvas.roundRect(left, bottom, card_width, card_height, 4.5, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor('#3f3f46'))
            canvas.setFont('InvoiceSansBold', 8.25)
            canvas.drawCentredString(left + card_width / 2, bottom + card_height - QR_PADDING - 8.25, LABELS['qr'])
            canvas.drawImage(ImageReader(BytesIO(b64decode(self.qr_code.split(',', 1)[1]))),
                             left + QR_PADDING, bottom + QR_PADDING + 12, QR_SIZE, QR_SIZE)
            canvas.setFillColor(BRAND)
            canvas.drawCentredString(left + card_width / 2, bottom + QR_PADDING + 1.5, LABELS['verifactu'])
        canvas.restoreState()
