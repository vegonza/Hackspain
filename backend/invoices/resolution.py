from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from postgrest.exceptions import APIError
from pydantic import BaseModel

from rules.models import Decision
from shared.logger import get_logger
from shared.storage import get_client


class ResolveInvoice(BaseModel):
    classification: Literal['PAGAR', 'NO_PAGAR']


def resolve_invoice(invoice_id: UUID, request: ResolveInvoice) -> Decision:
    try:
        result = get_client().rpc('resolve_invoice_decision', {
            'p_document_id': str(invoice_id),
            'p_classification': request.classification,
        }).execute().data
    except APIError as error:
        if error.message in ('invoice_not_reviewable', 'invoice_duplicate_payment', 'invoice_identity_required'):
            raise HTTPException(status_code=409, detail=error.message) from None
        raise
    decision = Decision.model_validate(result['decision'])
    get_logger().info('[INVOICES] Manually resolved %s: %s', result['name'], decision.classification)
    return decision
