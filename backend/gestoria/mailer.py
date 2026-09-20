import json
import os
from base64 import b64encode
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath

import httpx
from fastapi import HTTPException

from gestoria.models import Attachment, Email, Invoice
from shared.logger import get_logger
from shared.storage import download_file

# Leave room for MIME headers and base64 line wrapping under Resend's 40 MB limit.
MAX_ATTACHMENTS_SIZE = 30_000_000
LABELS: dict[str, str] = json.loads((Path(__file__).with_name('locales') / 'es.json').read_text())


class RejectedEmail(Exception):
    pass


def configuration() -> tuple[str, str]:
    try:
        return os.environ['RESEND_API_KEY'], os.environ['RESEND_FROM_EMAIL']
    except KeyError as error:
        raise HTTPException(409, 'gestoria_not_configured') from error


def batches(invoices: list[Invoice], keep_lock: Callable[[], None]) -> Iterator[tuple[list[Invoice], list[Attachment]]]:
    selected: list[Invoice] = []
    attachments: list[Attachment] = []
    size = 0
    for invoice in invoices:
        keep_lock()
        content = b64encode(download_file(invoice.path)).decode('ascii')
        if len(content) > MAX_ATTACHMENTS_SIZE:
            raise HTTPException(413, 'gestoria_file_too_large')
        if size + len(content) > MAX_ATTACHMENTS_SIZE:
            yield selected, attachments
            selected, attachments, size = [], [], 0
        name = PurePosixPath(invoice.name).stem
        filename = f'{invoice.kind}-{invoice.id}-{name}.pdf'
        attachments.append(Attachment(filename=filename, content=content))
        selected.append(invoice)
        size += len(content)
    if selected:
        yield selected, attachments


def make_email(sender: str, recipient: str, invoices: list[Invoice], attachments: list[Attachment]) -> Email:
    received = sum(invoice.kind == 'received' for invoice in invoices)
    issued = len(invoices) - received
    parts = [LABELS[f'{kind}_{"one" if count == 1 else "other"}'].format(count=count)
             for kind, count in [('received', received), ('issued', issued)] if count > 0]
    quantity = 'one' if len(invoices) == 1 else 'other'
    return Email(sender=sender, to=[recipient], subject=LABELS[f'subject_{quantity}'],
                 text=LABELS['body'].format(invoices=LABELS['conjunction'].join(parts)),
                 attachments=attachments)


def send_email(email: Email, api_key: str, identifier: str) -> None:
    try:
        response = httpx.post('https://api.resend.com/emails',
                              headers={'Authorization': f'Bearer {api_key}', 'Idempotency-Key': identifier},
                              json=email.model_dump(by_alias=True), timeout=30)
    except httpx.RequestError as error:
        get_logger().warning('[GESTORIA] Resend connection failed; preserving send for retry')
        raise HTTPException(409, 'gestoria_send_uncertain') from error
    if response.is_success:
        get_logger().info('[GESTORIA] Resend accepted email %s to %s', response.json()['id'], email.to[0])
        return
    get_logger().warning('[GESTORIA] Resend returned HTTP %s', response.status_code)
    if 400 <= response.status_code < 500 and response.status_code != 409:
        raise RejectedEmail()
    raise HTTPException(409, 'gestoria_send_uncertain')
