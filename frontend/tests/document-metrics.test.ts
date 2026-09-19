import { describe, expect, test } from 'bun:test'
import { documentStageMetrics, totalStageDuration } from '../src/hooks/documentMetrics'
import type { DocumentStage } from '../src/api/documents'

function extractionStage(cost: string | null): DocumentStage {
  return { id: 'extraction', status: 'ready', depends_on: ['text', 'ocr'], format: 'json',
    duration_ms: 6738, cost_usd: cost, content: '{}' }
}

describe('document processing costs', () => {
  test('uses the saved extraction price from detail even when the list still has no price', () => {
    const summary = { stage_metrics: [{ stage: 'extraction' as const, cost_usd: null, duration_ms: 6738 }] }
    const detail = { stages: [extractionStage('0.00041564')] }
    expect(documentStageMetrics(detail, summary)[0].cost_usd).toBe('0.00041564')
  })

  test('shows updated redo cost instead of the previous run price cached in the list', () => {
    const summary = { stage_metrics: [{ stage: 'extraction' as const, cost_usd: '0.00041564', duration_ms: 6738 }] }
    const detail = { stages: [extractionStage('0.00083128')] }
    expect(documentStageMetrics(detail, summary)[0].cost_usd).toBe('0.00083128')
  })

  test('keeps missing costs distinct from a reported zero cost', () => {
    expect(documentStageMetrics({ stages: [extractionStage(null)] }, undefined)[0].cost_usd).toBeNull()
    expect(documentStageMetrics({ stages: [extractionStage('0')] }, undefined)[0].cost_usd).toBe('0')
  })

  test('uses list metrics while detail is loading and does not invent metrics before either loads', () => {
    const summary = { stage_metrics: [{ stage: 'extraction' as const, cost_usd: '0.00041564', duration_ms: 6738 }] }
    expect(documentStageMetrics(null, summary)).toEqual(summary.stage_metrics)
    expect(documentStageMetrics(null, undefined)).toEqual([])
  })
})

describe('document processing duration', () => {
  test('sums the phase times even when upload-to-completion takes longer', () => {
    const document = {
      created_at: '2026-09-19T10:00:00Z', finished_at: '2026-09-19T10:01:36Z',
      stage_metrics: [3000, 0, 9000].map(duration_ms => ({ duration_ms })),
    }
    expect(totalStageDuration(document.stage_metrics)).toBe(12000)
  })

  test('does not invent a zero duration before any phase has metrics', () => {
    expect(totalStageDuration([])).toBeNull()
    expect(totalStageDuration([{ duration_ms: null }])).toBeNull()
    expect(totalStageDuration([{ duration_ms: 0 }, { duration_ms: null }])).toBe(0)
  })

  test('includes measured phases while other phases are pending', () => {
    expect(totalStageDuration([3100, 250, null].map(duration_ms => ({ duration_ms })))).toBe(3350)
    expect(totalStageDuration([3100, 250, 4500].map(duration_ms => ({ duration_ms })))).toBe(7850)
  })
})
