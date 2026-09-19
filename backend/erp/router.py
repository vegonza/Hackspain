from uuid import UUID

from fastapi import APIRouter

from erp.models import ErpEntryDetail, SavedErpSnapshot
from erp.repository import read_entry, read_latest_snapshot

router = APIRouter(prefix="/api/erp")


@router.get("/snapshot")
def get_snapshot() -> SavedErpSnapshot | None:
    return read_latest_snapshot()


@router.get("/entries/{entry_id}")
def get_entry(entry_id: UUID) -> ErpEntryDetail | None:
    return read_entry(entry_id)
