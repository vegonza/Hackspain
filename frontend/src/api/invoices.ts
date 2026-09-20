import { fetchJson, fetchBlob } from '@/api/client'

export interface PaymentDecision {
  classification: 'PAGAR' | 'NO_PAGAR' | 'ESCALAR'
  reasons: string[]
  checks: Record<string, boolean>
}

export interface InvoiceBilling {
  invoice_number: string | null
  supplier_name: string | null
  supplier_nif: string | null
  invoice_date: string | null
  purchase_order: string | null
  line_items: InvoiceLine[] | null
  currency: string | null
  tax_base: string | null
  total: string | null
  tax_base_eur: string | null
  total_eur: string | null
}

export interface Invoice {
  id: string
  name: string
  sha256: string
  created_at: string
  finished_at: string | null
  status: 'queued' | 'processing' | 'ready' | 'error'
  pages: number
  billing: InvoiceBilling | null
  payment_decision: PaymentDecision | null
  total_cost_usd: string | null
  total_duration_ms: number | null
  retry_attempts: number
  last_error: string | null
  next_retry_at: string | null
}

export type ErpWarning = 'missing_entry_id' | 'missing_supplier_id' | 'missing_tax_id' | 'missing_order_id'
  | 'missing_status' | 'missing_date' | 'missing_amount' | 'invalid_date' | 'date_out_of_range'
  | 'invalid_amount' | 'iso_date_format' | 'english_amount_format' | 'unknown_status' | 'possible_character_loss'

export interface InvoiceErpEntry {
  entry_id: string
  date: string | null
  supplier_id: string
  tax_id: string
  order_id: string
  amount: string | null
  raw_date: string
  raw_amount: string
  warnings: ErpWarning[]
  status: string
}

export interface InvoiceDetail extends Invoice {
  native_text: string | null
  extraction: InvoiceExtraction | null
  erp: InvoiceErpEntry | null
  erp_snapshot_id: string | null
}

export interface InvoiceLine {
  description: string
  amount: string
}

export interface InvoiceExtraction {
  invoice_number: string
  supplier_name: string
  supplier_nif: string
  iban: string
  invoice_date: string
  purchase_order: string
  currency: string
  line_items: InvoiceLine[]
  notes: string[]
  uncertainties: string[]
  tax_base: string
  vat_rate: string
  vat_amount: string
  total: string
}

export function fetchInvoices(): Promise<Invoice[]> {
  return fetchJson<Invoice[]>('/invoices')
}

export function fetchInvoice(id: string): Promise<InvoiceDetail> {
  return fetchJson<InvoiceDetail>(`/invoices/${id}`)
}

export function fetchPdfUrl(id: string): Promise<{ url: string }> {
  return fetchJson(`/invoices/${id}/pdf-url`)
}

export function deleteInvoice(id: string): Promise<{ deleted: boolean }> {
  return fetchJson(`/invoices/${id}`, { method: 'DELETE' })
}

export function retryInvoice(id: string): Promise<Invoice> {
  return fetchJson(`/invoices/${id}/retry`, { method: 'POST' })
}

export function redoInvoice(id: string): Promise<Invoice> {
  return fetchJson(`/invoices/${id}/redo`, { method: 'POST' })
}

export function uploadInvoice(file: File): Promise<Invoice> {
  const body = new FormData()
  body.append('file', file)
  return fetchJson<Invoice>('/invoices', { method: 'POST', body })
}

export function downloadInvoice(id: string): Promise<Blob> {
  return fetchBlob(`/invoices/${id}/download`)
}
