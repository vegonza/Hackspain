from fastapi import HTTPException
from postgrest.exceptions import APIError

from shared.logger import get_logger
from shared.storage import get_client
from orders.models import Order, OrderInput

logger = get_logger()


def list_orders() -> list[Order]:
    rows = get_client().table('orders').select('*').order('order_id').execute().data
    return [Order.model_validate(row) for row in rows]


def create_order(order: Order) -> Order:
    try:
        rows = get_client().table('orders').insert(order.model_dump(mode='json')).execute().data
    except APIError as error:
        if error.code == '23505':
            raise HTTPException(status_code=409, detail='order_exists') from None
        if error.code == '23503':
            raise HTTPException(status_code=422, detail='order_supplier_not_found') from None
        raise
    result = Order.model_validate(rows[0])
    logger.info('[ORDERS] Created %s (%s)', result.order_id, result.supplier_id)
    return result


def update_order(order_id: str, order: OrderInput) -> Order:
    try:
        rows = get_client().table('orders').update(order.model_dump(mode='json')).eq('order_id', order_id).execute().data
    except APIError as error:
        if error.code == '23503':
            raise HTTPException(status_code=422, detail='order_supplier_not_found') from None
        raise
    if not rows:
        raise HTTPException(status_code=404, detail='order_not_found')
    result = Order.model_validate(rows[0])
    logger.info('[ORDERS] Updated %s (%s)', order_id, result.supplier_id)
    return result


def delete_order(order_id: str) -> None:
    rows = get_client().table('orders').delete().eq('order_id', order_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail='order_not_found')
    logger.info('[ORDERS] Deleted %s', order_id)
