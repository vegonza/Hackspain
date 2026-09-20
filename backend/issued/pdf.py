from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

from issued.models import IssuedInvoice, line_amount
from issued.pdf_header import InvoiceHeader, MARGIN
from issued.pdf_labels import LABELS
from issued.pdf_table import InvoiceItems

pdfmetrics.registerFont(TTFont('InvoiceSans', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'))
pdfmetrics.registerFont(TTFont('InvoiceSansBold', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'))
BRAND = colors.HexColor('#214c70')
MUTED = colors.HexColor('#66726e')
BORDER = colors.HexColor('#dde3e0')
WIDTH = A4[0] - 2 * MARGIN


def money(value: Decimal, precision: int = 2) -> str:
    return f'{value:,.{precision}f}'.replace(',', '_').replace('.', ',').replace('_', '.') + ' €'


def render_invoice(invoice: IssuedInvoice, test_qr_code: str | None = None) -> bytes:
    buffer = BytesIO()
    document = BaseDocTemplate(buffer, pagesize=A4, title=invoice.invoice_number)
    body = ParagraphStyle('Body', fontName='InvoiceSans', fontSize=9.75, leading=14.5, textColor=colors.HexColor('#273633'))
    muted = ParagraphStyle('Muted', parent=body, fontSize=9, textColor=MUTED)
    label = ParagraphStyle('Label', parent=body, fontName='InvoiceSansBold', fontSize=7.5, textColor=BRAND, spaceAfter=6)
    bold = ParagraphStyle('Bold', parent=body, fontName='InvoiceSansBold')
    right = ParagraphStyle('Right', parent=body, alignment=TA_RIGHT)
    right_bold = ParagraphStyle('RightBold', parent=bold, alignment=TA_RIGHT)
    right_label = ParagraphStyle('RightLabel', parent=label, alignment=TA_RIGHT)

    def paragraph(value: str, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(escape(value).replace('\n', '<br/>'), style)

    header = InvoiceHeader(invoice.company.name, invoice.invoice_number, invoice.issue_date, test_qr_code)
    parties = Table([
        [paragraph(LABELS['issuer'], label), paragraph(LABELS['client'], label)],
        [paragraph(invoice.company.name, bold), paragraph(invoice.client.name, bold)],
        [paragraph(invoice.company.tax_id, muted), paragraph(invoice.client.tax_id, muted)],
        [paragraph(invoice.company.address, muted), paragraph(invoice.client.address, muted)],
        [paragraph(invoice.company.email, muted), paragraph(invoice.client.email, muted)],
    ], colWidths=[WIDTH / 2, WIDTH / 2])
    parties.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 18)]))
    dates = Table([[paragraph(f"{LABELS['issueDate']}: {invoice.issue_date:%d/%m/%Y}", muted),
                    paragraph(f"{LABELS['dueDate']}: {invoice.due_date:%d/%m/%Y}", muted)]], colWidths=[WIDTH / 2, WIDTH / 2])
    dates.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    content: list[Flowable] = [header, Spacer(1, 18), parties, Spacer(1, 18), dates,
                              Spacer(1, 21), paragraph(LABELS['concepts'], label)]
    rows = [[paragraph(LABELS[key], label if index == 0 else right_label) for index, key in enumerate(['description', 'quantity', 'unitPrice', 'taxRate', 'amount'])]]
    for item in invoice.items:
        rows.append([paragraph(item.description, bold), paragraph(format(item.quantity.normalize(), 'f'), right),
                     paragraph(money(item.unit_price, max(2, -item.unit_price.normalize().as_tuple().exponent)), right),
                     paragraph(f'{item.tax_rate.normalize():f} %', right), paragraph(money(line_amount(item)), right_bold)])
    items = InvoiceItems(rows, colWidths=[WIDTH * part / 100 for part in (36, 16, 16, 16, 16)], repeatRows=1, splitInRow=1, hAlign='LEFT')
    items.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fafafa')),
        ('BOX', (0, 0), (-1, -1), .5, BORDER), ('LINEBELOW', (0, 0), (-1, -1), .4, BORDER),
        ('LINEBELOW', (0, 1), (-1, -1), .4, BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))
    content.extend([items, Spacer(1, 6 * mm)])
    summary = Table([[paragraph(text, bold if i == 2 else muted), paragraph(money(value), right_bold if i == 2 else right)] for i, (text, value) in enumerate([
        (LABELS['base'], invoice.base_amount), (LABELS['tax'], invoice.tax_amount), (LABELS['total'], invoice.total_amount),
    ])], colWidths=[WIDTH * .32, WIDTH * .28], hAlign='RIGHT')
    summary.setStyle(TableStyle([('LINEABOVE', (0, 2), (-1, 2), .6, colors.HexColor('#b8c1c8')),
                                ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    closing: list[Flowable] = [summary]
    if invoice.company.payment_method or invoice.company.iban:
        closing.extend([Spacer(1, 9 * mm), paragraph(LABELS['paymentInfo'], label)])
        if invoice.company.payment_method:
            closing.append(paragraph(f"{LABELS['paymentMethod']}: {invoice.company.payment_method}", muted))
        if invoice.company.iban:
            closing.append(paragraph(f"{LABELS['iban']}: {invoice.company.iban}", muted))
    if invoice.notes:
        closing.extend([Spacer(1, 6 * mm), paragraph(invoice.notes, muted)])
    if test_qr_code is not None and invoice.verifactu_test is not None and invoice.verifactu_test.parties is not None:
        parties = invoice.verifactu_test.parties
        closing.extend([Spacer(1, 5 * mm), paragraph(LABELS['registration'], label),
                        paragraph(f"{LABELS['testIssuer']}: {parties.issuer.name} · {parties.issuer.tax_id}", muted),
                        paragraph(f"{LABELS['testClient']}: {parties.client.name} · {parties.client.tax_id}", muted)])
    content.append(KeepTogether(closing))

    def footer(canvas: Canvas, doc: BaseDocTemplate) -> None:
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.line(14 * mm, 17 * mm, A4[0] - 14 * mm, 17 * mm)
        canvas.setFont('InvoiceSans', 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(14 * mm, 11 * mm, LABELS['thanks'])
        canvas.drawRightString(A4[0] - 14 * mm, 11 * mm, invoice.company.name)
        canvas.restoreState()

    first = Frame(MARGIN, 24 * mm, WIDTH, A4[1] - 24 * mm,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    following = Frame(MARGIN, 24 * mm, WIDTH, A4[1] - 38 * mm,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    document.addPageTemplates([
        PageTemplate(id='first', frames=[first], onPage=footer, autoNextPageTemplate='following'),
        PageTemplate(id='following', frames=[following], onPage=footer),
    ])
    document.build(content)
    return buffer.getvalue()
