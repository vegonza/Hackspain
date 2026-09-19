from uuid import UUID

from rules.models import ResolvedReferences
from shared.identifiers import order_key
from shared.storage import get_client


def resolve_references(invoice_id: UUID, purchase_order: str) -> ResolvedReferences:
    """Resolve master data and every matching ERP entry from the invoice's pinned snapshot."""
    result = get_client().rpc('get_rule_references', {
        'p_document_id': str(invoice_id),
        'p_order_key': order_key(purchase_order),
    }).execute()
    return ResolvedReferences.model_validate(result.data)


def claim_order(invoice_id: UUID, purchase_order: str) -> UUID | None:
    result = get_client().rpc('claim_invoice_order', {
        'p_document_id': str(invoice_id), 'p_order_key': order_key(purchase_order),
    }).execute()
    return UUID(result.data) if result.data is not None else None
