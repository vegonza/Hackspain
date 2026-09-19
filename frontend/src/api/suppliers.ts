import { fetchJson } from '@/api/client'

export interface Supplier {
  supplier_id: string
  legal_name: string
  tax_id: string
  iban: string
  city: string
  payment_terms_days: number
}

export function fetchSuppliers(signal: AbortSignal): Promise<Supplier[]> {
  return fetchJson('/suppliers', { signal })
}

export function saveSupplier(id: string | null, supplier: Supplier): Promise<Supplier> {
  return fetchJson(id === null ? '/suppliers' : `/suppliers/${encodeURIComponent(id)}`, {
    method: id === null ? 'POST' : 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(supplier),
  })
}
