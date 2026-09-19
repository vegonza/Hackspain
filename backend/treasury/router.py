from datetime import date

from fastapi import APIRouter

from treasury.models import TreasuryReport
from treasury.repository import read_treasury

router = APIRouter(prefix="/api/treasury")


@router.get("")
def get_treasury() -> TreasuryReport:
    return read_treasury(date.today())
