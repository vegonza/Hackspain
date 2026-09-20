import { fetchJson, fetchEmpty } from '@/api/client'

export interface GestoriaInvoice { id: string; name: string; kind: 'received' | 'issued' }
export interface GestoriaStatus { kind: GestoriaInvoice['kind']; status: 'PAGAR' | 'paid'; count: number }
export interface GestoriaOverview { email: string; invoices: GestoriaInvoice[]; statuses: GestoriaStatus[] }
export interface GestoriaResult { sent: number }
export const fetchGestoria = (period: string, signal: AbortSignal): Promise<GestoriaOverview> => fetchJson(`/gestoria?${new URLSearchParams({ period })}`, { signal })
export const saveGestoria = (email: string): Promise<void> => fetchEmpty('/gestoria', {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }),
})
export const sendGestoria = (email: string, invoices: GestoriaInvoice[], period: string): Promise<GestoriaResult> => fetchJson('/gestoria/send', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, period, received_ids: invoices.filter(invoice => invoice.kind === 'received').map(invoice => invoice.id), issued_ids: invoices.filter(invoice => invoice.kind === 'issued').map(invoice => invoice.id) }),
})
