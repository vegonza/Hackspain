import { fetchEmpty, fetchJson } from '@/api/client'
import type { InvoiceErpEntry } from '@/api/invoices'

export interface ErpLinkedInvoice {
  id: string
  name: string
}

export interface ErpEntry extends InvoiceErpEntry {
  id: string
}

export interface ErpEntryDetail extends ErpEntry {
  invoices: ErpLinkedInvoice[]
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

export function refreshErpSnapshot(): Promise<void> {
  return fetchEmpty('/erp/snapshot', { method: 'POST' })
}
