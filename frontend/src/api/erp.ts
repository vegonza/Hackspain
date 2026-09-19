import { fetchJson } from '@/api/client'
import type { DocumentErpEntry } from '@/api/documents'

export interface ErpLinkedDocument {
  id: string
  name: string
}

export interface ErpEntry extends DocumentErpEntry {
  id: string
}

export interface ErpEntryDetail extends ErpEntry {
  documents: ErpLinkedDocument[]
}

export interface ErpSnapshot {
  id: string
  fetched_at: string
  erp_version: string
  update_loaded: boolean
  entry_count: number
  entries: ErpEntry[]
}

export function fetchErpSnapshot(): Promise<ErpSnapshot | null> {
  return fetchJson<ErpSnapshot | null>('/erp/snapshot')
}

export function fetchErpEntry(id: string): Promise<ErpEntryDetail | null> {
  return fetchJson<ErpEntryDetail | null>(`/erp/entries/${id}`)
}
