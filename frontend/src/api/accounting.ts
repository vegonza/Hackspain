import { fetchBlob, fetchJson } from '@/api/client'

export type ExpenseCategory = 'supplies' | 'professional_services' | 'rent' | 'repairs' | 'insurance'
  | 'banking' | 'advertising' | 'utilities' | 'travel' | 'meals' | 'vehicle' | 'other'
export type FiscalStatus = 'PREPARED' | 'REVIEW'
export type ReviewReason = 'missing_payment_decision' | 'payment_review' | 'missing_identity' | 'invalid_date'
  | 'missing_amounts' | 'invalid_tax_amounts' | 'sensitive_category' | 'unknown_category'

export interface AccountingSummary {
  recorded_expenses: string
  potential_deductible_expenses: string
  potential_deductible_vat: string
  amount_under_review: string
  prepared_invoices: number
  review_invoices: number
}

export interface CategorySummary {
  category: ExpenseCategory
  invoice_count: number
  tax_base: string
  vat_amount: string
  review_count: number
}

export interface FiscalInvoice {
  document_id: string
  document_name: string
  invoice_number: string | null
  invoice_date: string | null
  supplier_name: string | null
  supplier_nif: string | null
  category: ExpenseCategory
  account_code: string
  tax_base: string | null
  vat_rate: string | null
  vat_amount: string | null
  total: string | null
  potential_deductible_expense: string
  potential_deductible_vat: string
  status: FiscalStatus
  review_reasons: ReviewReason[]
}

export interface AccountingReport {
  year: number
  quarter: number | null
  summary: AccountingSummary
  by_category: CategorySummary[]
  invoices: FiscalInvoice[]
}

function query(year: number, quarter: number | null): string {
  return `year=${year}${quarter === null ? '' : `&quarter=${quarter}`}`
}

export function fetchAccounting(year: number, quarter: number | null, signal: AbortSignal): Promise<AccountingReport> {
  return fetchJson(`/accounting?${query(year, quarter)}`, { signal })
}

export function exportAccounting(year: number, quarter: number | null): Promise<Blob> {
  return fetchBlob(`/accounting/export?${query(year, quarter)}`)
}
