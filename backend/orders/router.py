from fastapi import APIRouter, Response

from orders import repository
from orders.models import Order, OrderInput

router = APIRouter(prefix='/api/orders')


@router.get('')
def list_orders() -> list[Order]:
    return repository.list_orders()


@router.post('', status_code=201)
def create_order(order: Order) -> Order:
    return repository.create_order(order)


@router.put('/{order_id}')
def update_order(order_id: str, order: OrderInput) -> Order:
    return repository.update_order(order_id, order)


@router.delete('/{order_id}', status_code=204)
def delete_order(order_id: str) -> Response:
    repository.delete_order(order_id)
    return Response(status_code=204)
