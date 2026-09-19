import { fetchJson } from '@/api/client'

export interface UsageRecord {
  id: string
  created_at: string
  invoice_name: string
  invoice_id: string
  provider: string
  model: string
  operation: string
  usage: { model: string; provider: string; cost: string; details: Record<string, unknown> }[]
}

export interface UsageResponse {
  records: UsageRecord[]
  total: number
  failed_pending: number
  page_size: number
  summary: { calls: number; pages: number; cost_usd: string; average_invoice_cost_usd: string }
  daily: { date: string; calls: number; cost_usd: string; operations: Record<string, string> }[]
}

export function fetchUsage(page: number): Promise<UsageResponse> {
  return fetchJson(`/usage?page=${page}`)
}

export function retryFailedUsage(): Promise<{ retried: number }> {
  return fetchJson('/usage/retry', { method: 'POST' })
}
