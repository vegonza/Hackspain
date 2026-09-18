import { fetchJson } from '@/api/client'

export interface Document {
  id: string
  name: string
  created_at: string
  status: 'queued' | 'processing' | 'ready' | 'error'
  pages: number
}

export interface DocumentDetail extends Document {
  markdown: string
  features: InvoiceFeatures | null
}

export interface InvoiceLine {
  description: string
  amount: string
}

export interface InvoiceFeatures {
  invoice_number: string
  supplier_name: string
  supplier_nif: string
  iban: string
  invoice_date: string
  purchase_order: string
  line_items: InvoiceLine[]
  tax_base: string
  vat_rate: string
  vat_amount: string
  total: string
}

export function fetchDocuments(): Promise<Document[]> {
  return fetchJson<Document[]>('/documents')
}

export function fetchDocument(id: string): Promise<DocumentDetail> {
  return fetchJson<DocumentDetail>(`/documents/${id}`)
}

export function fetchPdfUrl(id: string): Promise<{ url: string }> {
  return fetchJson(`/documents/${id}/pdf-url`)
}

export function deleteDocument(id: string): Promise<{ deleted: boolean }> {
  return fetchJson(`/documents/${id}`, { method: 'DELETE' })
}

export function uploadDocument(file: File): Promise<Document> {
  const body = new FormData()
  body.append('file', file)
  return fetchJson<Document>('/documents', { method: 'POST', body })
}
