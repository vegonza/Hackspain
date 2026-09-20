import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'

type Props = {
  values: { value: string; label: string; amount: string; count: string; incomplete: boolean; description: string }[]
  loading: boolean
  failed: boolean
}

export function InvoiceBillingSummary({ values, loading, failed }: Props) {
  return <dl className="billing-summary billing-received-summary" aria-live="polite">
    {values.map(summary => <div key={summary.value} data-summary={summary.value}>
      <dt>{summary.label}</dt>
      <dd>{loading ? <Skeleton className="h-4 w-20" /> : failed ? '—' : <Tooltip text={`${summary.count} · ${summary.description}`} asChild>
        <span>{summary.amount}{summary.incomplete && <span className="billing-incomplete">*</span>}</span>
      </Tooltip>}</dd>
    </div>)}
  </dl>
}
