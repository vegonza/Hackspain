import { Gauge, Timer } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import type { useAnalytics } from '@/hooks/useAnalytics'

type Props = Pick<ReturnType<typeof useAnalytics>, 'averageDurationLabel' | 'cadenceLabel' | 'loading' | 'labels'>

export function AnalyticsMetrics({ averageDurationLabel, cadenceLabel, loading, labels }: Props) {
  return <section className="analytics-metrics" aria-label={labels.metrics}>
    <article className="analytics-metric-card">
      <span className="analytics-metric-icon"><Timer size={20} aria-hidden="true" /></span>
      <div className="analytics-metric-copy">
        <span>{labels.averageDuration}</span>
        {loading ? <Skeleton className="h-7 w-24" /> : <strong>{averageDurationLabel}</strong>}
      </div>
    </article>
    <article className="analytics-metric-card">
      <span className="analytics-metric-icon"><Gauge size={20} aria-hidden="true" /></span>
      <div className="analytics-metric-copy">
        <span>{labels.estimatedCadence}</span>
        {loading ? <Skeleton className="h-7 w-24" /> : <strong>{cadenceLabel}</strong>}
      </div>
    </article>
  </section>
}
