from collections import Counter
from datetime import date
from typing import Any, Literal
from uuid import UUID

from gestoria.models import Invoice, Overview, SettingsInput, StatusCount
from shared.logger import get_logger
from shared.storage import get_client

PAGE_SIZE = 500


def read_settings() -> str:
    row = get_client().table('gestoria_settings').select('email').eq('id', True).single().execute().data
    return row['email']


def save_settings(value: SettingsInput) -> None:
    get_client().table('gestoria_settings').update({'email': value.email}).eq('id', True).execute()
    get_logger().info('[GESTORIA] Saved recipient %s', value.email)


def sendable_rows(kind: Literal['received', 'issued']) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        if kind == 'received':
            query = (get_client().table('documents').select('id,name,invoice_date')
                     .is_('deleted_at', 'null').eq('status', 'ready')
                     .eq('payment_decision->>classification', 'PAGAR'))
        else:
            query = get_client().table('issued_invoices').select('id,invoice_number,pdf_path,issue_date').eq('status', 'paid')
        page = query.is_('gestoria_sent_at', 'null').order('id').range(offset, offset + PAGE_SIZE - 1).execute().data
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def in_period(invoice_date: str | None, period: str) -> bool:
    if period == 'all':
        return True
    if invoice_date is None:
        return period == 'undated'
    try:
        dated = date.fromisoformat(invoice_date).isoformat() == invoice_date
    except ValueError:
        dated = False
    if period == 'undated':
        return not dated
    return dated and invoice_date[:7] == period


def eligible_invoices(period: str) -> list[Invoice]:
    received = [Invoice(id=row['id'], name=row['name'], kind='received', path=f"{row['id']}/original.pdf")
                for row in sendable_rows('received') if in_period(row['invoice_date'], period)]
    issued = [Invoice(id=row['id'], name=f"{row['invoice_number']}.pdf", kind='issued', path=row['pdf_path'])
              for row in sendable_rows('issued') if in_period(row['issue_date'], period)]
    return received + issued


def overview(period: str) -> Overview:
    invoices = eligible_invoices(period)
    counts = Counter(invoice.kind for invoice in invoices)
    statuses = [StatusCount(kind=kind, status='PAGAR' if kind == 'received' else 'paid', count=count) for kind, count in counts.items()]
    return Overview(email=read_settings(), invoices=invoices, statuses=statuses)


def mark_sent(received_ids: list[UUID], issued_ids: list[UUID]) -> None:
    get_client().rpc('mark_gestoria_sent', {
        'p_received_ids': [str(identifier) for identifier in received_ids],
        'p_issued_ids': [str(identifier) for identifier in issued_ids],
    }).execute()
