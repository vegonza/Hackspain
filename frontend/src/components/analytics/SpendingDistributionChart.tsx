import { ChartPie } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Sector, Tooltip } from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { SpendingDistributionTooltip } from '@/components/analytics/SpendingDistributionTooltip'
import type { useAnalytics } from '@/hooks/useAnalytics'

type Props = Pick<ReturnType<typeof useAnalytics>, 'items' | 'totalLabel' | 'activeIndex' | 'onActiveIndexChange' | 'loading' | 'labels'>

export function SpendingDistributionChart({ items, totalLabel, activeIndex, onActiveIndexChange, loading, labels }: Props) {
  return <article className="analytics-card">
    <header className="analytics-card-header">
      <ChartPie size={20} aria-hidden="true" />
      <h3>{labels.distribution}</h3>
    </header>
    {loading ? <div className="analytics-distribution">
      <Skeleton className="analytics-pie-skeleton" />
      <div className="analytics-legend">{Array.from({ length: 7 }, (_, index) => <Skeleton key={index} className="h-8 w-full" />)}</div>
    </div> : items.length === 0 ? <div className="analytics-empty">{labels.empty}</div> : <div className="analytics-distribution">
      <div className="analytics-pie">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip content={<SpendingDistributionTooltip />} isAnimationActive={false} />
            <Pie data={items} dataKey="amount" nameKey="label" innerRadius="58%" outerRadius="86%" paddingAngle={1}
              stroke="white" strokeWidth={2} onMouseEnter={(_, index) => onActiveIndexChange(index)}
              onMouseLeave={() => onActiveIndexChange(undefined)} isAnimationActive={false}
              shape={props => <Sector {...props} fillOpacity={activeIndex !== undefined && props.index !== activeIndex ? 0.28 : 1} />}>
              {items.map(item => <Cell key={item.category} fill={item.color} />)}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="analytics-pie-total analytics-spending-total"><span>{labels.total}</span><strong>{totalLabel}</strong></div>
      </div>
      <div className="analytics-legend">
        {items.map((item, index) => <button key={item.category} type="button"
          style={{ opacity: activeIndex !== undefined && activeIndex !== index ? 0.38 : 1 }}
          onPointerEnter={() => onActiveIndexChange(index)} onPointerLeave={() => onActiveIndexChange(undefined)}
          onFocus={() => onActiveIndexChange(index)} onBlur={() => onActiveIndexChange(undefined)}>
          <span className="analytics-legend-color" style={{ backgroundColor: item.color }} aria-hidden="true" />
          {item.icon !== null && <img className="analytics-legend-icon" src={item.icon} alt="" aria-hidden="true" />}
          <span className="analytics-legend-label">{item.label}</span>
          <strong>{item.amountLabel}</strong>
          <span>{item.percentageLabel}</span>
        </button>)}
      </div>
    </div>}
  </article>
}
