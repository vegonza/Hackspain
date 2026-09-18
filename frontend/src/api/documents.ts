import { fetchBlob, fetchJson } from '@/api/client'

export interface Document {
  id: string
  name: string
  created_at: string
  status: 'ready' | 'error'
  pages: number
}

export interface DocumentDetail extends Document {
  markdown: string
}

export function fetchDocuments(): Promise<Document[]> {
  return fetchJson<Document[]>('/documents')
}

export function fetchDocument(id: string): Promise<DocumentDetail> {
  return fetchJson<DocumentDetail>(`/documents/${id}`)
}

export function fetchPdf(id: string, signal: AbortSignal): Promise<Blob> {
  return fetchBlob(`/documents/${id}/pdf`, { signal })
}

export function deleteDocument(id: string): Promise<{ deleted: boolean }> {
  return fetchJson(`/documents/${id}`, { method: 'DELETE' })
}

export function uploadDocument(file: File): Promise<DocumentDetail> {
  const body = new FormData()
  body.append('file', file)
  return fetchJson<DocumentDetail>('/documents', { method: 'POST', body })
}
