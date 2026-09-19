from uuid import UUID

from rules.models import ResolvedReferences
from shared.identifiers import order_key
from shared.storage import get_client


def resolve_references(document_id: UUID, purchase_order: str) -> ResolvedReferences:
    """Resolve master data and every matching ERP entry from the document's pinned snapshot."""
    result = get_client().rpc('get_rule_references', {
        'p_document_id': str(document_id),
        'p_order_key': order_key(purchase_order),
    }).execute()
    return ResolvedReferences.model_validate(result.data)
