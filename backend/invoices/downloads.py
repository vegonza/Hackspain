from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from fastapi.responses import Response

from invoices.repository import read_invoice
from shared.logger import get_logger
from shared.storage import download_file


def download_pdf(invoice_id: UUID) -> Response:
    invoice = read_invoice(invoice_id)
    content = download_file(f"{invoice_id}/original.pdf")
    get_logger().info("[INVOICES] Downloaded %s", invoice.name)
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(Path(invoice.name).with_suffix('.pdf').name, safe='')}",
    })
