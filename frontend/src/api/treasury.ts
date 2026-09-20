import { fetchJson } from '@/api/client'

export interface TreasurySummary {
  next_7_days: string
  next_30_days: string
  blocked_in_review: string
}

export interface SupplierCommitment {
  supplier_name: string
  approved_invoices: number
  committed_amount: string
  next_due_date: string
}

export interface TreasuryPayment {
  document_id: string
  document_name: string
  supplier_name: string
  amount: string
  due_date: string
}

export interface TreasuryReport {
  summary: TreasurySummary
  by_supplier: SupplierCommitment[]
  payments: TreasuryPayment[]
}

export function fetchTreasury(signal: AbortSignal): Promise<TreasuryReport> {
  return fetchJson('/treasury', { signal })
}
