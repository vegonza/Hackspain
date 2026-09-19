from extractor.processor import process as extract_invoice
from invoices.decision import process as classify_invoice
from invoices.repository import InvoiceDetails


def process(invoice: InvoiceDetails) -> None:
    if invoice.result_path is None:
        extract_invoice(invoice)
    classify_invoice(invoice)
