import type { Document, DocumentDetail } from '@/api/documents'

export function documentStageMetrics(detail: Pick<DocumentDetail, 'stages'> | null, summary: Pick<Document, 'stage_metrics'> | undefined): Document['stage_metrics'] {
  if (detail !== null) {
    return detail.stages.map(stage => ({ stage: stage.id, cost_usd: stage.cost_usd, duration_ms: stage.duration_ms }))
  }
  return summary === undefined ? [] : summary.stage_metrics
}

export function totalStageDuration(metrics: readonly { duration_ms: number | null }[]): number | null {
  const durations = metrics.map(metric => metric.duration_ms).filter(duration => duration !== null)
  return durations.length === 0 ? null : durations.reduce((total, duration) => total + duration, 0)
}
