from typing import Annotated

from fastapi import APIRouter, Query, Response

from accounting.export import accounting_csv
from accounting.models import AccountingReport
from accounting.repository import read_accounting
from shared.logger import get_logger

router = APIRouter(prefix="/api/accounting")
Year = Annotated[int, Query(ge=2000, le=2100)]
Quarter = Annotated[int | None, Query(ge=1, le=4)]


@router.get("")
def get_accounting(year: Year, quarter: Quarter = None) -> AccountingReport:
    return read_accounting(year, quarter)


@router.get("/export")
def export_accounting(year: Year, quarter: Quarter = None) -> Response:
    report = read_accounting(year, quarter)
    suffix = f"-t{quarter}" if quarter is not None else ""
    filename = f"precierre-fiscal-{year}{suffix}.csv"
    get_logger().info("[ACCOUNTING] Exported %s invoice records to %s", len(report.invoices), filename)
    return Response(
        content=accounting_csv(report), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
