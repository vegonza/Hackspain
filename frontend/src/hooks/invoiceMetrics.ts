import type { Invoice } from '@/api/invoices'

type Metrics = Pick<Invoice, 'total_cost_usd' | 'total_duration_ms'>

export function invoiceMetrics(detail: Metrics | null, summary: Metrics | undefined): Metrics {
  if (detail !== null) return detail
  return summary === undefined ? { total_cost_usd: null, total_duration_ms: null } : summary
}
