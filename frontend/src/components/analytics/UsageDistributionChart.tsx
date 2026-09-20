import { CircleDollarSign } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Sector } from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import type { useAnalytics } from '@/hooks/useAnalytics'

type Props = Pick<ReturnType<typeof useAnalytics>, 'usageItems' | 'usageCenterLabel' | 'usageCenterAmountLabel' | 'usageActiveIndex' | 'onUsageActiveIndexChange' | 'loading' | 'labels'>

export function UsageDistributionChart({ usageItems, usageCenterLabel, usageCenterAmountLabel, usageActiveIndex, onUsageActiveIndexChange, loading, labels }: Props) {
  return <article className="analytics-card analytics-vat-card">
    <header className="analytics-card-header">
      <CircleDollarSign size={20} aria-hidden="true" />
      <h3>{labels.usage}</h3>
    </header>
    {loading ? <div className="analytics-vat-distribution">
      <Skeleton className="analytics-vat-pie-skeleton" />
      <div className="analytics-vat-legend"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>
    </div> : usageItems.length === 0 ? <div className="analytics-empty">{labels.usageEmpty}</div>
      : <div className="analytics-vat-distribution">
        <div className="analytics-vat-pie">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={usageItems} dataKey="amount" nameKey="label" innerRadius="62%" outerRadius="88%" paddingAngle={2}
                stroke="white" strokeWidth={2} isAnimationActive={false}
                onMouseEnter={(_, index) => onUsageActiveIndexChange(index)} onMouseLeave={() => onUsageActiveIndexChange(undefined)}
                shape={props => <Sector {...props} fillOpacity={usageActiveIndex !== undefined && props.index !== usageActiveIndex ? 0.28 : 1} />}>
                {usageItems.map(item => <Cell key={item.id} fill={item.color} />)}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="analytics-pie-total"><span>{usageCenterLabel}</span><strong>{usageCenterAmountLabel}</strong></div>
        </div>
        <div className="analytics-vat-legend">
          {usageItems.map((item, index) => <button key={item.id} type="button"
            style={{ opacity: usageActiveIndex !== undefined && usageActiveIndex !== index ? 0.38 : 1 }}
            onPointerEnter={() => onUsageActiveIndexChange(index)} onPointerLeave={() => onUsageActiveIndexChange(undefined)}
            onFocus={() => onUsageActiveIndexChange(index)} onBlur={() => onUsageActiveIndexChange(undefined)}>
            <span style={{ backgroundColor: item.color }} aria-hidden="true" />
            <span>{item.label}</span>
            <strong>{item.amountLabel}</strong>
            <small>{item.percentageLabel}</small>
          </button>)}
        </div>
      </div>}
  </article>
}
