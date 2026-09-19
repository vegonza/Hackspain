interface Props {
  entries: { model: string; cost: string; details: { label: string; value: string }[] }[]
  total: string
  totalLabel: string
}

export function UsageCostBreakdown({ entries, total, totalLabel }: Props) {
  return <div className="space-y-2 text-left text-xs">
    {entries.map((entry, index) => <div key={index} className="space-y-1">
      <div className="flex justify-between gap-4 font-medium"><span>{entry.model}</span><span>{entry.cost}</span></div>
      <dl className="text-muted-foreground">{entry.details.map(detail => <div key={detail.label} className="flex justify-between gap-4"><dt>{detail.label}</dt><dd>{detail.value}</dd></div>)}</dl>
    </div>)}
    <div className="flex justify-between gap-4 border-t pt-2 font-medium"><span>{totalLabel}</span><span>{total}</span></div>
  </div>
}
