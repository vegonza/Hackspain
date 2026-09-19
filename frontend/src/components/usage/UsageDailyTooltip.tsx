import type { useUsage } from '@/hooks/useUsage'

interface Props {
  active?: boolean
  payload?: readonly { payload: ReturnType<typeof useUsage>['daily'][number] }[]
  costLabel: string
}

export function UsageDailyTooltip({ active, payload, costLabel }: Props) {
  if (!active || !payload || payload.length === 0) return null
  const day = payload[0].payload
  return <div className="rounded-lg border border-border bg-background px-3 py-2 text-xs shadow-md">
    <p className="mb-1.5 font-medium">{day.dateLabel}</p>
    {day.breakdown.map(item => <div key={item.operation} className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-1.5"><span className="size-2 rounded-full" style={{ backgroundColor: item.color }} aria-hidden="true" /><span className="text-muted-foreground">{item.operation}</span></div>
      <span className="tabular-nums">{item.cost}</span>
    </div>)}
    <div className="mt-1.5 flex justify-between gap-4 border-t border-border pt-1.5 font-medium"><span>{costLabel}</span><span className="tabular-nums">{day.totalLabel}</span></div>
  </div>
}
