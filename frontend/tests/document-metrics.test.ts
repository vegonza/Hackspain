import { describe, expect, test } from 'bun:test'
import { totalStageDuration } from '../src/hooks/documentMetrics'

describe('document processing duration', () => {
  test('sums the phase times even when upload-to-completion takes longer', () => {
    const document = {
      created_at: '2026-09-19T10:00:00Z', finished_at: '2026-09-19T10:01:36Z',
      stage_metrics: [3000, 0, 3000, 9000].map(duration_ms => ({ duration_ms })),
    }
    expect(totalStageDuration(document.stage_metrics)).toBe(15000)
  })

  test('does not invent a zero duration before any phase has metrics', () => {
    expect(totalStageDuration([])).toBeNull()
    expect(totalStageDuration([{ duration_ms: null }])).toBeNull()
    expect(totalStageDuration([{ duration_ms: 0 }, { duration_ms: null }])).toBe(0)
  })

  test('includes measured phases while other phases are pending', () => {
    expect(totalStageDuration([3100, 250, null, null].map(duration_ms => ({ duration_ms })))).toBe(3350)
    expect(totalStageDuration([3100, 250, 4500, null].map(duration_ms => ({ duration_ms })))).toBe(7850)
  })
})
