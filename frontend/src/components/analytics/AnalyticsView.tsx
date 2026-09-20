import { Button } from '@/components/ui/button'
import { SpendingDistributionChart } from '@/components/analytics/SpendingDistributionChart'
import { VatDeductionChart } from '@/components/analytics/VatDeductionChart'
import { UsageDistributionChart } from '@/components/analytics/UsageDistributionChart'
import type { useAnalytics } from '@/hooks/useAnalytics'

export function AnalyticsView({ mount, failed, onRetry, labels, ...chart }: ReturnType<typeof useAnalytics>) {
  return <section className="analytics-view" ref={mount} aria-label={labels.title} aria-busy={chart.loading}>
    <header className="table-toolbar"><div className="table-toolbar-content"><h2>{labels.title}</h2></div></header>
    <div className="analytics-content">
      {failed ? <div role="alert" className="analytics-error"><span>{labels.failed}</span><Button variant="outline" onClick={onRetry}>{labels.retry}</Button></div>
        : <>
          <SpendingDistributionChart {...chart} labels={labels} />
          <VatDeductionChart {...chart} labels={labels} />
          <UsageDistributionChart {...chart} labels={labels} />
          <SpendingDistributionChart loading={chart.loading} items={chart.supplierItems} totalLabel={chart.supplierTotalLabel}
            activeIndex={chart.supplierActiveIndex} onActiveIndexChange={chart.onSupplierActiveIndexChange}
            labels={{ ...labels, distribution: labels.supplierDistribution, empty: labels.supplierEmpty }} />
        </>}
    </div>
  </section>
}
