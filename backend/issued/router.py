from uuid import UUID
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from issued import repository
from issued.models import Client, Company, InvoiceInput, IssuedInvoice, IssuedInvoiceSummary, Party
from issued.pdf import render_invoice
from issued.verifactu import require_test_environment, submit_test, test_enabled
from shared.redis import get_redis
from shared.logger import get_logger
from shared.storage import download_file, upload_file

router = APIRouter(prefix='/api/billing', tags=['billing'])


@router.get('/clients')
def clients() -> list[Client]:
    return repository.list_clients()


@router.post('/clients', status_code=201)
def create_client(party: Party) -> Client:
    return repository.create_client(party)


@router.put('/clients/{client_id}')
def update_client(client_id: UUID, party: Party) -> Client:
    return repository.update_client(client_id, party)


@router.delete('/clients/{client_id}', status_code=204)
def delete_client(client_id: UUID) -> Response:
    repository.delete_client(client_id)
    return Response(status_code=204)


@router.get('/company')
def company() -> Company | None:
    return repository.read_company()


@router.put('/company')
def save_company(value: Company) -> Company:
    return repository.save_company(value)


@router.get('/invoices')
def invoices() -> list[IssuedInvoiceSummary]:
    return repository.list_invoices()


@router.get('/invoices/{invoice_id}')
def invoice(invoice_id: UUID) -> IssuedInvoice:
    return repository.read_invoice(invoice_id)


@router.post('/invoices/{invoice_id}/issue')
def issue(invoice_id: UUID, body: InvoiceInput) -> IssuedInvoice:
    with get_redis() as redis, redis.lock(f'billing:verifactu-test:{invoice_id}', timeout=300):
        value = repository.reserve_invoice(invoice_id, body)
        if test_enabled():
            value = prepare_test_invoice(value)
        elif value.status == 'issuing':
            get_logger().info('[BILLING] Preparing PDF %s for %s', value.invoice_number, value.client.name)
            upload_file(f'issued/{value.id}/invoice.pdf', render_invoice(value), 'application/pdf')
        if value.status in ('issued', 'paid'):
            return value
        return repository.finish_invoice(value, f'issued/{value.id}/invoice.pdf')


def prepare_test_invoice(value: IssuedInvoice) -> IssuedInvoice:
    receipt = value.verifactu_test
    if receipt is None or receipt.csv is None:
        receipt = submit_test(value)
        value = repository.save_verifactu_test(value, receipt)
    if receipt.pdf_path is None:
        content = render_invoice(value, test_qr_code=receipt.qr_code)
        path = f'issued/{value.id}/invoice.pdf'
        upload_file(path, content, 'application/pdf')
        receipt.pdf_path = path
        value = repository.save_verifactu_test(value, receipt)
    return value


@router.post('/invoices/{invoice_id}/paid')
def paid(invoice_id: UUID) -> IssuedInvoice:
    return repository.mark_paid(invoice_id)


@router.get('/invoices/{invoice_id}/pdf')
def pdf(invoice_id: UUID) -> Response:
    value = repository.read_invoice(invoice_id)
    if test_enabled() and (value.verifactu_test is None or value.verifactu_test.csv is None):
        raise HTTPException(409, 'verifactu_test_pending')
    if value.pdf_path is None:
        raise HTTPException(409, 'issued_invoice_pdf_pending')
    content = download_file(value.pdf_path)
    get_logger().info('[BILLING] Downloaded %s for %s', value.invoice_number, value.client.name)
    return Response(content, media_type='application/pdf', headers={
        'Content-Disposition': f"attachment; filename*=UTF-8''{quote(value.invoice_number, safe='')}.pdf",
    })


@router.get('/settings')
def settings() -> dict[str, bool]:
    return {'verifactu_test_enabled': test_enabled()}


@router.post('/invoices/{invoice_id}/verifactu-test')
def verifactu_test(invoice_id: UUID) -> IssuedInvoice:
    require_test_environment()
    with get_redis() as redis, redis.lock(f'billing:verifactu-test:{invoice_id}', timeout=300):
        value = repository.read_invoice(invoice_id)
        if value.status not in ('issued', 'paid'):
            raise HTTPException(409, 'issued_invoice_locked')
        return prepare_test_invoice(value)


@router.get('/invoices/{invoice_id}/verifactu-test/pdf')
def verifactu_test_pdf(invoice_id: UUID) -> Response:
    require_test_environment()
    value = repository.read_invoice(invoice_id)
    if value.verifactu_test is None or value.verifactu_test.csv is None:
        raise HTTPException(409, 'verifactu_test_pending')
    if value.verifactu_test.pdf_path is None:
        raise HTTPException(409, 'issued_invoice_pdf_pending')
    content = download_file(value.verifactu_test.pdf_path)
    get_logger().info('[BILLING] Downloaded Veri*Factu TEST PDF %s', value.invoice_number)
    return Response(content, media_type='application/pdf', headers={
        'Content-Disposition': f"attachment; filename*=UTF-8''{quote(str(value.invoice_number), safe='')}-test.pdf",
    })
