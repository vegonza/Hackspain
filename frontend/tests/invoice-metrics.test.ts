import { describe, expect, test } from 'bun:test'
import { invoiceMetrics } from '../src/hooks/invoiceMetrics'

describe('document metrics', () => {
  test('uses fresh detail instead of stale list metrics after reprocessing', () => {
    const detail = { total_cost_usd: '0.002', total_duration_ms: 8000 }
    const summary = { total_cost_usd: '0.001', total_duration_ms: 7000 }
    expect(invoiceMetrics(detail, summary)).toEqual(detail)
  })

  test('preserves missing metrics instead of inventing zero cost or duration', () => {
    const detail = { total_cost_usd: null, total_duration_ms: null }
    expect(invoiceMetrics(detail, { total_cost_usd: '0.001', total_duration_ms: 7000 })).toEqual(detail)
    expect(invoiceMetrics(null, undefined)).toEqual(detail)
    expect(invoiceMetrics({ total_cost_usd: '0', total_duration_ms: 0 }, undefined)).toEqual({ total_cost_usd: '0', total_duration_ms: 0 })
  })

  test('uses the summary while detail loads', () => {
    const summary = { total_cost_usd: '0.001', total_duration_ms: 7000 }
    expect(invoiceMetrics(null, summary)).toEqual(summary)
  })
})
