import { ApiError, fetchBlob, fetchEmpty, fetchJson } from '@/api/client'

export interface BillingParty { name: string; tax_id: string; address: string; email: string; logo_url: string }
export interface BillingClient extends BillingParty { id: string }
export interface BillingCompany extends BillingParty { iban: string; payment_method: string }
export interface IssuedLine { description: string; quantity: string; unit_price: string; tax_rate: string }
export interface IssuedDraft { client_id: string; issue_date: string; due_date: string; notes: string; items: IssuedLine[] }
export interface IssuedInvoice extends IssuedDraft {
  id: string
  status: 'issuing' | 'issued' | 'paid'
  invoice_number: string
  company: BillingCompany
  client: BillingParty
  base_amount: string
  tax_amount: string
  total_amount: string
  pdf_path: string | null
  created_at: string
  paid_at: string | null
  verifactu_test: { parties: { issuer: { name: string; tax_id: string }; client: { name: string; tax_id: string } } | null; qr_code: string; csv: string | null; submitted_at: string | null; pdf_path: string | null } | null
}
export type IssuedInvoiceSummary = Pick<IssuedInvoice, 'id' | 'status' | 'invoice_number' | 'issue_date' | 'client' | 'items' | 'base_amount' | 'total_amount' | 'pdf_path'>

export function isUnreservedInvoiceError(error: unknown): boolean {
  return error instanceof ApiError && (
    (error.status === 422 && Array.isArray(error.detail))
    || (error.status === 404 && error.detail === 'billing_client_not_found')
    || (error.status === 409 && error.detail === 'billing_company_required')
  )
}

const json = (method: string, body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const fetchIssuedInvoices = (signal: AbortSignal): Promise<IssuedInvoiceSummary[]> => fetchJson('/billing/invoices', { signal })
export const fetchBillingClients = (signal: AbortSignal): Promise<BillingClient[]> => fetchJson('/billing/clients', { signal })
export const fetchBillingCompany = (signal: AbortSignal): Promise<BillingCompany | null> => fetchJson('/billing/company', { signal })
export const createBillingClient = (party: BillingParty): Promise<BillingClient> => fetchJson('/billing/clients', json('POST', party))
export const deleteBillingClient = (id: string): Promise<void> => fetchEmpty(`/billing/clients/${id}`, { method: 'DELETE' })
export const fetchIssuedInvoice = (id: string, signal: AbortSignal): Promise<IssuedInvoice> => fetchJson(`/billing/invoices/${id}`, { signal })
export const issueInvoice = (id: string, draft: IssuedDraft): Promise<IssuedInvoice> => fetchJson(`/billing/invoices/${id}/issue`, json('POST', draft))
export const markInvoicePaid = (id: string): Promise<IssuedInvoice> => fetchJson(`/billing/invoices/${id}/paid`, { method: 'POST' })
export const downloadIssuedInvoice = (id: string): Promise<Blob> => fetchBlob(`/billing/invoices/${id}/pdf`)

export const updateBillingClient = (id: string, party: BillingParty): Promise<BillingClient> => fetchJson(`/billing/clients/${id}`, json('PUT', party))

export const fetchBillingSettings = (signal: AbortSignal): Promise<{ verifactu_test_enabled: boolean }> => fetchJson('/billing/settings', { signal })
export const submitVerifactuTest = (id: string): Promise<IssuedInvoice> => fetchJson(`/billing/invoices/${id}/verifactu-test`, { method: 'POST' })
