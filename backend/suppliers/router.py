from fastapi import APIRouter, Response

from suppliers import repository
from suppliers.models import Supplier, SupplierInput

router = APIRouter(prefix='/api/suppliers')


@router.get('')
def list_suppliers() -> list[Supplier]:
    return repository.list_suppliers()


@router.post('', status_code=201)
def create_supplier(supplier: Supplier) -> Supplier:
    return repository.create_supplier(supplier)


@router.put('/{supplier_id}')
def update_supplier(supplier_id: str, supplier: SupplierInput) -> Supplier:
    return repository.update_supplier(supplier_id, supplier)


@router.delete('/{supplier_id}', status_code=204)
def delete_supplier(supplier_id: str) -> Response:
    repository.delete_supplier(supplier_id)
    return Response(status_code=204)
