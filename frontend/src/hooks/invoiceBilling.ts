import type { Invoice, PaymentDecision } from '@/api/invoices'

export type BillingInvoice = Pick<Invoice, 'id' | 'name' | 'created_at' | 'billing' | 'payment_decision' | 'last_error' | 'next_retry_at'> & {
  status: Invoice['status'] | 'uploading'
}
export type BillingDecision = 'PAGAR' | 'ESCALAR' | 'NO_PAGAR' | 'pending'
export type BillingSort = 'supplier' | 'review' | 'date' | 'amount'

export function invoiceDate(invoice: BillingInvoice): string | null {
  const value = invoice.billing === null ? null : invoice.billing.invoice_date
  if (value === null || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value ? null : value
}

export function billingDecision(invoice: BillingInvoice): BillingDecision {
  if (invoice.status !== 'ready' || invoice.payment_decision === null) return 'pending'
  return invoice.payment_decision.classification
}

export function normalizeSearch(value: string): string {
  return value.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase('es-ES')
}

export function matchesInvoice(invoice: BillingInvoice, search: string): boolean {
  const billing = invoice.billing
  const values = [invoice.id, invoice.name]
  if (billing !== null) {
    values.push(...[billing.supplier_name, billing.supplier_nif, billing.invoice_number, billing.purchase_order]
      .filter((value): value is string => value !== null))
    if (billing.line_items !== null) values.push(...billing.line_items.map(line => line.description))
  }
  const text = normalizeSearch(values.join(' '))
  return normalizeSearch(search).trim().split(/\s+/).every(word => text.includes(word))
}

export function periodInvoices(invoices: BillingInvoice[], period: string): BillingInvoice[] {
  return invoices.filter(invoice => {
    const date = invoiceDate(invoice)
    return period === 'all' || (period === 'undated' ? date === null : date !== null && date.startsWith(period))
  })
}

export function euroTotal(invoices: BillingInvoice[]): { cents: number; unknown: number; count: number } {
  let cents = 0
  let unknown = 0
  for (const invoice of invoices) {
    const amount = invoice.billing === null ? null : invoice.billing.total_eur
    if (amount === null) unknown++
    else cents += Math.round(Number(amount) * 100)
  }
  return { cents, unknown, count: invoices.length }
}

export function sortInvoices(invoices: BillingInvoice[], column: BillingSort | null, direction: 'asc' | 'desc'): BillingInvoice[] {
  if (column === null) return invoices
  const value = (invoice: BillingInvoice): string | number | null => {
    if (column === 'review') return billingDecision(invoice)
    if (column === 'date') return invoiceDate(invoice)
    if (invoice.billing === null) return null
    if (column === 'amount') return invoice.billing.tax_base_eur === null ? null : Number(invoice.billing.tax_base_eur)
    return invoice.billing.supplier_name
  }
  return [...invoices].sort((left, right) => {
    const a = value(left), b = value(right)
    if (a === null) return b === null ? left.name.localeCompare(right.name) : 1
    if (b === null) return -1
    const comparison = typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b), 'es', { numeric: true })
    return (direction === 'asc' ? comparison : -comparison) || left.name.localeCompare(right.name, 'es', { numeric: true })
  })
}

export function shiftMonth(month: string, delta: number): string {
  const [year, index] = month.split('-').map(Number)
  const date = new Date(Date.UTC(year, index - 1 + delta, 1))
  return date.toISOString().slice(0, 7)
}

export interface BillingRow {
  id: string
  partyName: string
  initials: string | null
  logo: string | undefined
  secondary: string
  date: string
  amount: string
  gross: string
  originalAmount: string | null
  href: string
  canOpen: boolean
  badge: {
    label: string
    description: string
    tone: 'neutral' | 'success' | 'warning' | 'error'
    icon: 'spinner' | 'clock' | 'error' | null
    processing: boolean
    status: string
    classification: PaymentDecision['classification'] | null
  }
}
