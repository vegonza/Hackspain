import { UsageLogTable } from '@/components/usage/UsageLogTable'
import type { useUsage } from '@/hooks/useUsage'
import { Skeleton } from '@/components/ui/skeleton'
import { UsageDailyChart } from '@/components/usage/UsageDailyChart'
import { Button } from '@/components/ui/button'

export function UsageView({ mount, loading, failed, stats, daily, records, page, pages, setPage, labels, totalLabel, failedPending, pendingError, onRetry, retrying }: ReturnType<typeof useUsage>) {
  return <section className="usage-view" ref={mount} aria-label={labels.title} aria-busy={loading}>
    <div className="usage-stats">
      {loading ? Array.from({ length: 3 }, (_, index) => <Skeleton key={index} className="h-20 w-full" />)
        : stats.map(stat => <div key={stat.label}><span>{stat.label}</span><strong>{stat.value}</strong></div>)}
    </div>
    {failed && <p role="alert" className="markdown-error">{labels.failed}</p>}
    {failedPending > 0 && <div role="alert" className="flex items-center justify-between gap-3 px-4 py-2 text-sm"><span>{pendingError}</span><Button variant="outline" size="sm" disabled={retrying} onClick={() => void onRetry()}>{labels.retry}</Button></div>}
    <UsageDailyChart {...{ daily, loading, labels }} />
    <UsageLogTable {...{ loading, records, page, pages, setPage, labels, totalLabel }} />
  </section>
}
