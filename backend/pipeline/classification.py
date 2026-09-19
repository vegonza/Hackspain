from datetime import datetime, timezone

from invoices.classification import classify_invoice
from invoices.repository import InvoiceDetails
from pipeline.extraction_3.extraction import InvoiceExtraction
from pipeline.extraction_3.extractor import MODEL
from rules.models import Decision
from shared.identifiers import order_key
from shared.logger import get_logger
from shared.storage import download_file, get_client
from shared.usage import track_usage

logger = get_logger()


def process(invoice_record: InvoiceDetails) -> None:
    """Publish a decision only after extraction is saved; the classifier atomically claims the order."""
    if invoice_record.payment_decision is not None:
        return
    invoice = InvoiceExtraction.model_validate_json(download_file(f'{invoice_record.id}/extraction/features.json'))
    with track_usage('openrouter', MODEL, 'classification', str(invoice_record.id), invoice_record.name) as usage:
        decision = classify_invoice(invoice_record.id, invoice, datetime.now(timezone.utc).date(),
                                     usage=usage)
    result = get_client().rpc('publish_payment_decision', {
        'p_document_id': str(invoice_record.id), 'p_order_key': order_key(invoice.purchase_order),
        'p_decision': decision.model_dump(mode='json', by_alias=True),
    }).execute()
    invoice_record.payment_decision = Decision.model_validate(result.data)
    logger.info('[RULES] Published %s: %s', invoice_record.name, invoice_record.payment_decision.classification)
