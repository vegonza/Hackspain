from fastapi import APIRouter

from erp.models import SavedErpSnapshot
from erp.repository import read_latest_snapshot

router = APIRouter(prefix="/api/erp")


@router.get("/snapshot")
def get_snapshot() -> SavedErpSnapshot | None:
    return read_latest_snapshot()
