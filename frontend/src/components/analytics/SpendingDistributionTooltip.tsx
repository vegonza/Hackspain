import type { useAnalytics } from '@/hooks/useAnalytics'

interface Props {
  active?: boolean
  payload?: readonly { payload: ReturnType<typeof useAnalytics>['items'][number] }[]
}

export function SpendingDistributionTooltip({ active, payload }: Props) {
  if (!active || !payload || payload.length === 0) return null
  const item = payload[0].payload
  return <div className="rounded-lg border border-border bg-background px-3 py-2 text-xs shadow-md">
    <div className="mb-1.5 flex items-center gap-2 font-medium"><span className="size-2 rounded-sm" style={{ backgroundColor: item.color }} />{item.label}</div>
    <div className="flex items-center justify-between gap-6"><span className="text-muted-foreground">{item.percentageLabel}</span><span className="tabular-nums">{item.amountLabel}</span></div>
  </div>
}
