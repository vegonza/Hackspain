import { fetchJson } from '@/api/client'

export interface Document {
  id: string
  name: string
  sha256: string
  created_at: string
  status: 'queued' | 'processing' | 'ready' | 'error'
  pages: number
  retry_attempts: number
  last_error: string | null
  next_retry_at: string | null
}

export type StageId = 'ocr' | 'text' | 'merge'
export type StageStatus = 'queued' | 'processing' | 'ready' | 'error' | 'retrying' | 'unavailable'

export interface DiffLine {
  kind: 'equal' | 'removed' | 'added'
  text: string
  before: number | null
  after: number | null
}

export interface DocumentStage {
  id: StageId
  status: StageStatus
  depends_on: StageId[]
  format: 'markdown' | 'text'
  duration_ms: number | null
  cost_usd: string | null
  content: string | null
  diff: DiffLine[] | null
}

export interface DocumentDetail extends Document {
  stages: DocumentStage[]
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

export function retryDocument(id: string): Promise<Document> {
  return fetchJson(`/documents/${id}/retry`, { method: 'POST' })
}

export function uploadDocument(file: File): Promise<Document> {
  const body = new FormData()
  body.append('file', file)
  return fetchJson<Document>('/documents', { method: 'POST', body })
}

export function fetchStageCosts(id: string): Promise<Record<string, string>> {
  return fetchJson(`/documents/${id}/stage-costs`)
}
