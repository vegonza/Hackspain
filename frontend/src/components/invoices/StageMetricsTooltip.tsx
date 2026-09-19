type Props = { rows: { label: string; value: string }[]; total: string; title: string }

export function StageMetricsTooltip({ rows, total, title }: Props) {
  return <div className="space-y-2 text-left text-xs">
    <dl className="space-y-1 text-muted-foreground">
      {rows.map(row => <div key={row.label} className="flex justify-between gap-6"><dt>{row.label}</dt><dd className="tabular-nums">{row.value}</dd></div>)}
    </dl>
    <div className="flex justify-between gap-6 border-t pt-2 font-medium"><span>{title}</span><span className="tabular-nums">{total}</span></div>
  </div>
}
