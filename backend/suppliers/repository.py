from fastapi import HTTPException
from postgrest.exceptions import APIError

from shared.logger import get_logger
from shared.storage import get_client
from suppliers.models import Supplier, SupplierInput

logger = get_logger()


def list_suppliers() -> list[Supplier]:
    suppliers: list[Supplier] = []
    while True:
        rows = get_client().table('suppliers').select('*').order('supplier_id').range(
            len(suppliers), len(suppliers) + 999,
        ).execute().data
        suppliers.extend(Supplier.model_validate(row) for row in rows)
        if len(rows) < 1000:
            return suppliers


def create_supplier(supplier: Supplier) -> Supplier:
    try:
        rows = get_client().table('suppliers').insert(supplier.model_dump()).execute().data
    except APIError as error:
        if error.code == '23505':
            raise HTTPException(status_code=409, detail='supplier_exists') from None
        raise
    result = Supplier.model_validate(rows[0])
    logger.info('[SUPPLIERS] Created %s (%s)', result.legal_name, result.supplier_id)
    return result


def update_supplier(supplier_id: str, supplier: SupplierInput) -> Supplier:
    rows = get_client().table('suppliers').update(supplier.model_dump()).eq('supplier_id', supplier_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail='supplier_not_found')
    result = Supplier.model_validate(rows[0])
    logger.info('[SUPPLIERS] Updated %s (%s)', result.legal_name, supplier_id)
    return result


def delete_supplier(supplier_id: str) -> None:
    try:
        rows = get_client().table('suppliers').delete().eq('supplier_id', supplier_id).execute().data
    except APIError as error:
        if error.code == '23503':
            raise HTTPException(status_code=409, detail='supplier_has_orders') from None
        raise
    if not rows:
        raise HTTPException(status_code=404, detail='supplier_not_found')
    logger.info('[SUPPLIERS] Deleted %s (%s)', rows[0]['legal_name'], supplier_id)
