import { fetchJson } from '@/api/client'
import type { InvoiceCategory } from '@/api/invoices'

export interface CategorySpending {
  category: InvoiceCategory
  amount_eur: string
}

export interface SpendingDistribution {
  total_eur: string
  categories: CategorySpending[]
}

export interface VatDeduction {
  total_eur: string
  deductible_eur: string
  foreign_eur: string
}

export type UsageOperation = 'extraction' | 'classification' | 'categorization'

export interface UsageDistribution {
  average_document_cost_usd: string
  operations: { operation: UsageOperation; average_document_cost_usd: string }[]
}

export interface AnalyticsOverview {
  spending: SpendingDistribution
  vat: VatDeduction
  usage: UsageDistribution
  processing: {
    average_duration_ms: string | null
    seconds_per_invoice: string | null
    workers: number
  }
}

export function fetchAnalytics(): Promise<AnalyticsOverview> {
  return fetchJson('/analytics')
}
