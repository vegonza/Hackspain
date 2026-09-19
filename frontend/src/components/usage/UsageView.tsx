import { UsageLogTable } from '@/components/usage/UsageLogTable'
import type { useUsage } from '@/hooks/useUsage'
import { Skeleton } from '@/components/ui/skeleton'
import { UsageDailyChart } from '@/components/usage/UsageDailyChart'

export function UsageView({ mount, loading, failed, stats, daily, records, page, pages, setPage, labels, totalLabel }: ReturnType<typeof useUsage>) {
  return <section className="usage-view" ref={mount} aria-label={labels.title} aria-busy={loading}>
    <div className="usage-stats">
      {loading ? Array.from({ length: 3 }, (_, index) => <Skeleton key={index} className="h-20 w-full" />)
        : stats.map(stat => <div key={stat.label}><span>{stat.label}</span><strong>{stat.value}</strong></div>)}
    </div>
    {failed && <p role="alert" className="markdown-error">{labels.failed}</p>}
    <UsageDailyChart {...{ daily, loading, labels }} />
    <UsageLogTable {...{ loading, records, page, pages, setPage, labels, totalLabel }} />
  </section>
}
