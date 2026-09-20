from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from postgrest.exceptions import APIError

from issued.models import Client, Company, InvoiceInput, IssuedInvoice, IssuedInvoiceSummary, Party, VerifactuTestReceipt
from shared.logger import get_logger
from shared.storage import get_client


def list_invoices() -> list[IssuedInvoiceSummary]:
    result: list[IssuedInvoiceSummary] = []
    columns = ','.join(IssuedInvoiceSummary.model_fields)
    while True:
        rows = get_client().table('issued_invoices').select(columns).order('issue_date', desc=True).order('id').range(len(result), len(result) + 999).execute().data
        result.extend(IssuedInvoiceSummary.model_validate(row) for row in rows)
        if len(rows) < 1000:
            return result


def read_invoice(invoice_id: UUID) -> IssuedInvoice:
    rows = get_client().table('issued_invoices').select('*').eq('id', str(invoice_id)).execute().data
    if not rows:
        raise HTTPException(404, 'issued_invoice_not_found')
    return IssuedInvoice.model_validate(rows[0])


def list_clients() -> list[Client]:
    result: list[Client] = []
    while True:
        rows = get_client().table('billing_clients').select('*').order('name').order('id').range(len(result), len(result) + 999).execute().data
        result.extend(Client.model_validate(row) for row in rows)
        if len(rows) < 1000:
            return result


def create_client(party: Party) -> Client:
    try:
        row = get_client().table('billing_clients').insert(party.model_dump()).execute().data[0]
    except APIError as error:
        if error.code == '23505':
            raise HTTPException(409, 'billing_client_exists') from None
        raise
    client = Client.model_validate(row)
    get_logger().info('[BILLING] Created client %s', client.name)
    return client


def read_company() -> Company | None:
    rows = get_client().table('billing_company').select('*').eq('id', True).execute().data
    return Company.model_validate(rows[0]) if rows else None


def save_company(company: Company) -> Company:
    get_client().table('billing_company').upsert({'id': True, **company.model_dump()}).execute()
    get_logger().info('[BILLING] Saved company %s', company.name)
    return company


def reserve_invoice(invoice_id: UUID, value: InvoiceInput) -> IssuedInvoice:
    try:
        data = get_client().rpc('reserve_issued_invoice', {'p_id': str(invoice_id), 'p_invoice': value.model_dump(mode='json')}).execute().data
    except APIError as error:
        if error.code == 'P0001':
            raise HTTPException(409, 'billing_company_required') from None
        if error.code == 'P0002':
            raise HTTPException(404, 'billing_client_not_found') from None
        raise
    invoice = IssuedInvoice.model_validate(data)
    get_logger().info('[BILLING] Reserved invoice %s for %s', invoice.invoice_number, invoice.client.name)
    return invoice


def finish_invoice(invoice: IssuedInvoice, path: str) -> IssuedInvoice:
    get_client().table('issued_invoices').update({'status': 'issued', 'pdf_path': path}).eq('id', str(invoice.id)).eq('status', 'issuing').execute()
    get_logger().info('[BILLING] Issued %s for %s', invoice.invoice_number, invoice.client.name)
    return read_invoice(invoice.id)


def mark_paid(invoice_id: UUID) -> IssuedInvoice:
    get_client().table('issued_invoices').update({'status': 'paid', 'paid_at': datetime.now(timezone.utc).isoformat()}).eq('id', str(invoice_id)).eq('status', 'issued').execute()
    invoice = read_invoice(invoice_id)
    if invoice.status != 'paid':
        raise HTTPException(409, 'issued_invoice_locked')
    get_logger().info('[BILLING] Marked %s as paid for %s', invoice.invoice_number, invoice.client.name)
    return invoice


def update_client(client_id: UUID, party: Party) -> Client:
    try:
        rows = get_client().table('billing_clients').update(party.model_dump()).eq('id', str(client_id)).execute().data
    except APIError as error:
        if error.code == '23505':
            raise HTTPException(409, 'billing_client_exists') from None
        raise
    if not rows:
        raise HTTPException(404, 'billing_client_not_found')
    client = Client.model_validate(rows[0])
    get_logger().info('[BILLING] Updated client %s', client.name)
    return client


def delete_client(client_id: UUID) -> None:
    try:
        rows = get_client().table('billing_clients').delete().eq('id', str(client_id)).execute().data
    except APIError as error:
        if error.code == '23503':
            raise HTTPException(409, 'billing_client_has_invoices') from None
        raise
    if not rows:
        raise HTTPException(404, 'billing_client_not_found')
    get_logger().info('[BILLING] Deleted client %s', rows[0]['name'])


def save_verifactu_test(invoice: IssuedInvoice, receipt: VerifactuTestReceipt) -> IssuedInvoice:
    rows = get_client().table('issued_invoices').update({'verifactu_test': receipt.model_dump(mode='json')}).eq('id', str(invoice.id)).execute().data
    get_logger().info('[BILLING] Saved Veri*Factu TEST result for %s', invoice.invoice_number)
    return IssuedInvoice.model_validate(rows[0])
