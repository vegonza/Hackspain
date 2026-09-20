import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx
from fastapi import HTTPException

from issued.models import IssuedInvoice, TestTaxParties, TestTaxParty, VerifactuTestReceipt, line_amount
from shared.logger import get_logger

TEST_ENDPOINT = 'https://facturae.irenesolutions.com:8050/Kivu/Taxes/Verifactu/Invoices/Create'


def test_enabled() -> bool:
    return os.environ['ENV'] in ('development', 'test')


def require_test_environment() -> None:
    if not test_enabled():
        raise HTTPException(403, 'verifactu_test_only')


def submit_test(invoice: IssuedInvoice) -> VerifactuTestReceipt:
    require_test_environment()
    parties = TestTaxParties(
        issuer=TestTaxParty(name=os.environ['VERIFACTU_TEST_SELLER_NAME'], tax_id=os.environ['VERIFACTU_TEST_SELLER_ID']),
        client=TestTaxParty(name=os.environ['VERIFACTU_TEST_BUYER_NAME'], tax_id=os.environ['VERIFACTU_TEST_BUYER_ID']),
    )
    by_rate: dict[Decimal, tuple[Decimal, Decimal]] = {}
    for item in invoice.items:
        base = line_amount(item)
        tax = (base * item.tax_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        previous_base, previous_tax = by_rate.get(item.tax_rate, (Decimal(0), Decimal(0)))
        by_rate[item.tax_rate] = (previous_base + base, previous_tax + tax)
    payload: dict[str, Any] = {
        'ServiceKey': os.environ['VERIFACTU_SERVICE_KEY'], 'Status': 'POST', 'InvoiceType': 'F1',
        'InvoiceID': invoice.invoice_number, 'InvoiceDate': invoice.issue_date.isoformat(),
        'SellerID': parties.issuer.tax_id, 'CompanyName': parties.issuer.name,
        'RelatedPartyID': parties.client.tax_id, 'RelatedPartyName': parties.client.name,
        'Text': invoice.items[0].description,
        'TaxItems': [{'TaxScheme': '01', 'TaxType': 'S1', 'TaxRate': float(rate), 'TaxBase': float(base), 'TaxAmount': float(tax)}
                     for rate, (base, tax) in by_rate.items()],
    }
    get_logger().info('[BILLING] Submitting %s to Veri*Factu TEST for %s', invoice.invoice_number, invoice.client.name)
    try:
        response = httpx.post(TEST_ENDPOINT, json=payload, timeout=30, follow_redirects=False)
        response.raise_for_status()
        result = response.json()['Return']
    except (httpx.HTTPError, ValueError, KeyError):
        get_logger().error('[BILLING] Veri*Factu TEST request failed for %s', invoice.invoice_number)
        raise HTTPException(502, 'verifactu_test_failed') from None
    if result.get('ErrorCode'):
        get_logger().error('[BILLING] Veri*Factu TEST rejected %s (code %s)', invoice.invoice_number, result['ErrorCode'])
        raise HTTPException(422, f"verifactu_test_rejected: {result['ErrorDescription']}")
    if result.get('StatusResponse') != 'Correcto' or not result.get('QrCode') or not result.get('CSV'):
        raise HTTPException(502, 'verifactu_test_failed')
    return VerifactuTestReceipt(parties=parties, qr_code=f"data:image/bmp;base64,{result['QrCode']}",
                                csv=result['CSV'], submitted_at=datetime.now(timezone.utc), pdf_path=None)
