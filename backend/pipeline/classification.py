from datetime import datetime, timezone

from documents.classification import classify_document
from documents.repository import DocumentDetails
from pipeline.extraction_3.extraction import InvoiceExtraction
from pipeline.extraction_3.extractor import MODEL
from rules.models import Decision
from shared.identifiers import order_key
from shared.logger import get_logger
from shared.storage import download_file, get_client
from shared.usage import track_usage

logger = get_logger()


def process(document: DocumentDetails) -> None:
    """Publish a decision only after extraction is saved; the classifier atomically claims the order."""
    if document.payment_decision is not None:
        return
    invoice = InvoiceExtraction.model_validate_json(download_file(f'{document.id}/extraction/features.json'))
    with track_usage('openrouter', MODEL, 'classification', str(document.id), document.name) as usage:
        decision = classify_document(document.id, invoice, datetime.now(timezone.utc).date(),
                                     usage=usage)
    result = get_client().rpc('publish_payment_decision', {
        'p_document_id': str(document.id), 'p_order_key': order_key(invoice.purchase_order),
        'p_decision': decision.model_dump(mode='json'),
    }).execute()
    document.payment_decision = Decision.model_validate(result.data)
    logger.info('[RULES] Published %s: %s', document.name, document.payment_decision.classification)
