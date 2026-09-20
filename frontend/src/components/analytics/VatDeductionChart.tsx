import { ReceiptText } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Sector } from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import type { useAnalytics } from '@/hooks/useAnalytics'

type Props = Pick<ReturnType<typeof useAnalytics>, 'vatItems' | 'vatCenterLabel' | 'vatCenterAmountLabel' | 'vatActiveIndex' | 'onVatActiveIndexChange' | 'loading' | 'labels'>

export function VatDeductionChart({ vatItems, vatCenterLabel, vatCenterAmountLabel, vatActiveIndex, onVatActiveIndexChange, loading, labels }: Props) {
  return <article className="analytics-card analytics-vat-card">
    <header className="analytics-card-header">
      <ReceiptText size={20} aria-hidden="true" />
      <h3>{labels.vat}</h3>
    </header>
    {loading ? <div className="analytics-vat-distribution">
      <Skeleton className="analytics-vat-pie-skeleton" />
      <div className="analytics-vat-legend"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>
    </div> : vatItems.length === 0 ? <div className="analytics-empty">{labels.vatEmpty}</div>
      : <div className="analytics-vat-distribution">
        <div className="analytics-vat-pie">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={vatItems} dataKey="amount" nameKey="label" innerRadius="62%" outerRadius="88%" paddingAngle={2}
                stroke="white" strokeWidth={2} isAnimationActive={false}
                onMouseEnter={(_, index) => onVatActiveIndexChange(index)} onMouseLeave={() => onVatActiveIndexChange(undefined)}
                shape={props => <Sector {...props} fillOpacity={vatActiveIndex !== undefined && props.index !== vatActiveIndex ? 0.28 : 1} />}>
                {vatItems.map(item => <Cell key={item.id} fill={item.color} />)}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="analytics-pie-total"><span>{vatCenterLabel}</span><strong>{vatCenterAmountLabel}</strong></div>
        </div>
        <div className="analytics-vat-legend">
          {vatItems.map((item, index) => <button key={item.id} type="button"
            style={{ opacity: vatActiveIndex !== undefined && vatActiveIndex !== index ? 0.38 : 1 }}
            onPointerEnter={() => onVatActiveIndexChange(index)} onPointerLeave={() => onVatActiveIndexChange(undefined)}
            onFocus={() => onVatActiveIndexChange(index)} onBlur={() => onVatActiveIndexChange(undefined)}>
            <span style={{ backgroundColor: item.color }} aria-hidden="true" />
            <span>{item.label}</span>
            <strong>{item.amountLabel}</strong>
            <small>{item.percentageLabel}</small>
          </button>)}
        </div>
      </div>}
  </article>
}
