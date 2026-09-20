import { describe, expect, test } from 'bun:test'
import { billingDecision, euroTotal, invoiceDate, matchesInvoice, periodInvoices, shiftMonth, sortInvoices, type BillingInvoice } from '../src/hooks/invoiceBilling'

const invoice: BillingInvoice = {
  id: '1', name: 'scan.pdf', created_at: '2026-09-20T10:00:00Z', status: 'ready', last_error: null, next_retry_at: null,
  payment_decision: { classification: 'PAGAR', reasons: [], checks: { not_paid: true } },
  billing: { invoice_number: 'FA-9117', supplier_name: 'Papelería Ruzafa', supplier_nif: 'J40112358',
    invoice_date: '2026-06-12', purchase_order: 'PO-1317', line_items: [{ description: 'Servicio profesional', amount: '680' }],
    currency: 'EUR', tax_base: '680', total: '822.80', tax_base_eur: '680', total_eur: '822.80' },
}

describe('billing periods, search and totals', () => {
  test('groups by invoice month rather than upload date', () => {
    expect(periodInvoices([invoice], '2026-06')).toEqual([invoice])
    expect(periodInvoices([invoice], '2026-09')).toEqual([])
    expect(periodInvoices([invoice], 'all')).toEqual([invoice])
  })
  test('keeps unprocessed and invalid dates in the undated view', () => {
    const pending = { ...invoice, billing: null, status: 'processing' as const }
    const invalid = { ...invoice, billing: { ...invoice.billing!, invoice_date: '2026-02-30' } }
    expect(invoiceDate(invalid)).toBeNull()
    expect(periodInvoices([invoice, pending, invalid], 'undated')).toEqual([pending, invalid])
    expect(invoiceDate({ ...invoice, billing: { ...invoice.billing!, invoice_date: 'not a date' } })).toBeNull()
  })
  test('searches business fields, concepts and filenames without accents', () => {
    for (const query of ['papeleria', 'J40112358', 'FA-9117', 'PO-1317', 'profesional', 'scan.pdf', 'scan', 'ruzafa 9117']) {
      expect(matchesInvoice(invoice, query)).toBe(true)
    }
    expect(matchesInvoice(invoice, 'unknown')).toBe(false)
    expect(matchesInvoice({ ...invoice, id: 'ef6c24dd-9b6e-456a-b425-bf242150684f' }, 'EF6C24DD-9B6E-456A-B425-BF242150684F')).toBe(true)
    expect(matchesInvoice({ ...invoice, id: 'ef6c24dd-9b6e-456a-b425-bf242150684f', billing: null }, 'ef6c24dd')).toBe(true)
  })
  test('distinguishes recommendation from paid ERP entries and incomplete processing', () => {
    expect(billingDecision(invoice)).toBe('PAGAR')
    expect(billingDecision({ ...invoice, payment_decision: { classification: 'NO_PAGAR', reasons: [], checks: { not_paid: false } } })).toBe('paid')
    expect(billingDecision({ ...invoice, payment_decision: { classification: 'NO_PAGAR', reasons: [], checks: { not_paid: true } } })).toBe('NO_PAGAR')
    expect(billingDecision({ ...invoice, status: 'processing' })).toBe('pending')
  })
  test('sums stored EUR amounts and counts unknown conversions without treating them as zero', () => {
    const foreign = { ...invoice, billing: { ...invoice.billing!, currency: 'USD', total: '100', total_eur: '92' } }
    const unknown = { ...invoice, billing: { ...invoice.billing!, currency: 'MXN', total: '900', total_eur: null } }
    expect(euroTotal([invoice, foreign, unknown])).toEqual({ cents: 91480, unknown: 1, count: 3 })
    expect(euroTotal([{ ...invoice, billing: null }])).toEqual({ cents: 0, unknown: 1, count: 1 })
  })
  test('sorts by the displayed pre-tax EUR amount even when gross totals order differently', () => {
    const smaller = { ...invoice, id: '2', billing: { ...invoice.billing!, tax_base_eur: '679', total_eur: '900' } }
    const unknown = { ...invoice, id: '3', billing: null }
    expect(sortInvoices([unknown, invoice, smaller], 'amount', 'asc').map(row => row.id)).toEqual(['2', '1', '3'])
    expect(sortInvoices([unknown, smaller, invoice], 'amount', 'desc').map(row => row.id)).toEqual(['1', '2', '3'])
  })
  test('month navigation crosses year boundaries', () => {
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
    expect(shiftMonth('2026-12', 1)).toBe('2027-01')
  })
})
