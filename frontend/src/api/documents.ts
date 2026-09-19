import { fetchJson } from '@/api/client'

export interface Document {
  id: string
  name: string
  sha256: string
  created_at: string
  finished_at: string | null
  status: 'queued' | 'processing' | 'ready' | 'error'
  pages: number
  total_cost_usd: string | null
  stage_metrics: { stage: StageId; cost_usd: string | null; duration_ms: number | null }[]
  current_stages: StageId[]
  retry_attempts: number
  last_error: string | null
  next_retry_at: string | null
}

export type StageId = 'ocr' | 'text' | 'merge' | 'extraction'
export type StageStatus = 'queued' | 'processing' | 'ready' | 'error' | 'retrying' | 'unavailable'

export interface DiffLine {
  kind: 'equal' | 'removed' | 'added'
  text: string
  before: number | null
  after: number | null
  spans: { text: string; changed: boolean }[]
}

export interface DocumentStage {
  id: StageId
  status: StageStatus
  depends_on: StageId[]
  format: 'markdown' | 'text' | 'json'
  duration_ms: number | null
  cost_usd: string | null
  content: string | null
  diff: DiffLine[] | null
}

export type ErpWarning = 'missing_entry_id' | 'missing_supplier_id' | 'missing_tax_id' | 'missing_order_id'
  | 'missing_status' | 'missing_date' | 'missing_amount' | 'invalid_date' | 'date_out_of_range'
  | 'invalid_amount' | 'iso_date_format' | 'english_amount_format' | 'unknown_status' | 'possible_character_loss'

export interface DocumentErpEntry {
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

export interface DocumentDetail extends Document {
  stages: DocumentStage[]
  features: InvoiceFeatures | null
  erp: DocumentErpEntry | null
  erp_snapshot_id: string | null
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
  notes: string[]
  uncertainties: string[]
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
