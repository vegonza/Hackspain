import { CircleDollarSign } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Sector } from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { AnalyticsMetrics } from '@/components/analytics/AnalyticsMetrics'
import type { useAnalytics } from '@/hooks/useAnalytics'

type Props = Pick<ReturnType<typeof useAnalytics>, 'usageItems' | 'usageCenterLabel' | 'usageCenterAmountLabel' | 'usageActiveIndex' | 'onUsageActiveIndexChange' | 'loading' | 'labels' | 'averageDurationLabel' | 'cadenceLabel'>

export function UsageDistributionChart({ usageItems, usageCenterLabel, usageCenterAmountLabel, usageActiveIndex, onUsageActiveIndexChange, loading, labels, averageDurationLabel, cadenceLabel }: Props) {
  return <article className="analytics-card analytics-usage-card">
    <header className="analytics-card-header">
      <CircleDollarSign size={20} aria-hidden="true" />
      <h3>{labels.usage}</h3>
    </header>
    <div className="analytics-vat-distribution analytics-usage-distribution">
      {loading ? <Skeleton className="analytics-vat-pie-skeleton" />
        : usageItems.length === 0 ? <div className="analytics-empty">{labels.usageEmpty}</div>
        : <div className="analytics-vat-pie">
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
        </div>}
      <div className="analytics-usage-sidebar">
        <div className="analytics-vat-legend">
          {loading ? <><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></>
            : usageItems.map((item, index) => <button key={item.id} type="button"
              style={{ opacity: usageActiveIndex !== undefined && usageActiveIndex !== index ? 0.38 : 1 }}
              onPointerEnter={() => onUsageActiveIndexChange(index)} onPointerLeave={() => onUsageActiveIndexChange(undefined)}
              onFocus={() => onUsageActiveIndexChange(index)} onBlur={() => onUsageActiveIndexChange(undefined)}>
              <span style={{ backgroundColor: item.color }} aria-hidden="true" />
              <span>{item.label}</span>
              <strong>{item.amountLabel}</strong>
              <small>{item.percentageLabel}</small>
            </button>)}
        </div>
        <AnalyticsMetrics loading={loading} labels={labels} averageDurationLabel={averageDurationLabel} cadenceLabel={cadenceLabel} />
      </div>
    </div>
  </article>
}
