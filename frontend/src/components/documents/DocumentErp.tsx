import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'

type Props = {
  title: string
  loading: boolean
  rows: { label: string; value: string }[]
}

export function DocumentErp({ title, loading, rows }: Props) {
  return (
    <section className="document-data" aria-label={title} aria-busy={loading}>
      <header className="review-header"><h2>{title}</h2></header>
      <div className="extraction-view">
        <dl className="extraction-grid">
          {rows.map(row => <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>{loading ? <Skeleton className="ml-auto h-3 w-20" /> : <Tooltip text={row.value} onlyWhenTruncated asChild><span className="block truncate">{row.value}</span></Tooltip>}</dd>
          </div>)}
        </dl>
      </div>
    </section>
  )
}
