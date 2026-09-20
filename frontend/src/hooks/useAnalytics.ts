import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchAnalytics, type AnalyticsOverview, type UsageOperation } from '@/api/analytics'
import type { InvoiceCategory } from '@/api/invoices'
import { formatAmount } from '@/lib/format'
import { invoiceCategoryIcon } from '@/lib/invoiceCategory'
import { supplierLogo } from '@/lib/supplierLogos'

const categoryColors = {
  officeSupplies: '#2f6b5f',
  maintenance: '#4f86c6',
  recurringServices: '#6f8a3d',
  inspection: '#c59b35',
  supplies: '#3a9d8f',
  installation: '#d17a4f',
  cleaning: '#3e8fa3',
  transport: '#c95f5f',
  technicalSupport: '#4676a8',
  professionalServices: '#a56f3f',
  other: '#8a8a8a',
} satisfies Record<InvoiceCategory, string>

const operationColors = {
  extraction: categoryColors.maintenance,
  classification: categoryColors.officeSupplies,
  categorization: categoryColors.installation,
} satisfies Record<UsageOperation, string>

const percentage = new Intl.NumberFormat('es-ES', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

const dollars = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  currencyDisplay: 'narrowSymbol',
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
})

const cadence = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 3,
})

export function useAnalytics() {
  const { t } = useTranslation()
  const [data, setData] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [activeIndex, setActiveIndex] = useState<number>()
  const [vatActiveIndex, setVatActiveIndex] = useState<number>()
  const [usageActiveIndex, setUsageActiveIndex] = useState<number>()
  const [supplierActiveIndex, setSupplierActiveIndex] = useState<number>()
  const mounted = useRef(false)
  const requestVersion = useRef(0)
  const load = useCallback(async (): Promise<void> => {
    const version = ++requestVersion.current
    setLoading(true)
    setFailed(false)
    try {
      const result = await fetchAnalytics()
      if (mounted.current && version === requestVersion.current) setData(result)
    } catch {
      if (mounted.current && version === requestVersion.current) setFailed(true)
    } finally {
      if (mounted.current && version === requestVersion.current) setLoading(false)
    }
  }, [])
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    mounted.current = true
    void load()
    return () => { mounted.current = false; ++requestVersion.current }
  }, [load])

  const spendingTotal = data === null ? 0 : Number(data.spending.total_eur)
  const items = (data === null ? [] : data.spending.categories).map(item => {
      const amount = Number(item.amount_eur)
      const ratio = amount / spendingTotal
      return {
        ...item,
        id: item.category,
        amount,
        amountLabel: formatAmount(amount, 'EUR'),
        icon: invoiceCategoryIcon(item.category),
        percentageLabel: percentage.format(ratio),
        label: t(`extraction.categories.${item.category}`),
        color: categoryColors[item.category],
      }
    })
  const supplierTotal = data === null ? 0 : Number(data.supplier_spending.total_eur)
  const supplierItems = (data === null ? [] : data.supplier_spending.suppliers).map((item, index) => {
    const amount = Number(item.amount_eur)
    const logo = supplierLogo(item.supplier_name)
    return {
      id: item.supplier_key, amount, amountLabel: formatAmount(amount, 'EUR'),
      label: item.supplier_name === null ? t('analytics.unknownSupplier') : item.supplier_name,
      icon: logo === undefined ? null : logo,
      percentageLabel: percentage.format(amount / supplierTotal),
      color: `hsl(${(155 + index * 137.508) % 360} 42% 45%)`,
    }
  })
  const vatItems = data === null ? [] : [
    { id: 'deductible', amount: Number(data.vat.deductible_eur), color: categoryColors.officeSupplies, label: t('analytics.deductibleSpain') },
    { id: 'foreign', amount: Number(data.vat.foreign_eur), color: categoryColors.inspection, label: t('analytics.foreignVat') },
  ].filter(item => item.amount > 0).map(item => {
    const ratio = item.amount / Number(data.vat.total_eur)
    return {
      ...item,
      amountLabel: formatAmount(item.amount, 'EUR'),
      percentageLabel: percentage.format(ratio),
    }
  })
  const vatCenter = vatActiveIndex === undefined
    ? { label: t('analytics.deductibleSpain'), amountLabel: formatAmount(data === null ? 0 : Number(data.vat.deductible_eur), 'EUR') }
    : vatItems[vatActiveIndex]
  const usageTotal = data === null ? 0 : Number(data.usage.average_document_cost_usd)
  const usageItems = (data === null ? [] : data.usage.operations).map(item => {
    const amount = Number(item.average_document_cost_usd)
    return {
      id: item.operation,
      amount,
      amountLabel: dollars.format(amount),
      percentageLabel: percentage.format(amount / usageTotal),
      label: t(`usage.operations.${item.operation}`),
      color: operationColors[item.operation],
    }
  })
  const usageCenter = usageActiveIndex === undefined
    ? { label: t('analytics.averageCost'), amountLabel: dollars.format(usageTotal) }
    : usageItems[usageActiveIndex]
  const averageDuration = data === null || data.processing.average_duration_ms === null
    ? null
    : Number(data.processing.average_duration_ms)
  const durationCentiseconds = averageDuration === null ? null : Math.round(averageDuration / 10)
  const averageDurationLabel = durationCentiseconds === null ? '—' : durationCentiseconds < 6000
    ? t('processing.durationSeconds', { value: (durationCentiseconds / 100).toFixed(2) })
    : t('processing.durationMinutes', { minutes: Math.floor(durationCentiseconds / 6000), seconds: ((durationCentiseconds % 6000) / 100).toFixed(2) })
  const cadenceLabel = data === null || data.processing.seconds_per_invoice === null
    ? '—'
    : t('analytics.cadenceValue', { value: cadence.format(Number(data.processing.seconds_per_invoice)) })
  return {
    mount, loading, failed, activeIndex,
    onActiveIndexChange: setActiveIndex,
    onRetry: () => void load(),
    totalLabel: formatAmount(spendingTotal, 'EUR'),
    items,
    supplierItems, supplierTotalLabel: formatAmount(supplierTotal, 'EUR'),
    supplierActiveIndex, onSupplierActiveIndexChange: setSupplierActiveIndex,
    vatActiveIndex,
    onVatActiveIndexChange: setVatActiveIndex,
    vatItems,
    vatCenterLabel: vatCenter.label,
    vatCenterAmountLabel: vatCenter.amountLabel,
    usageActiveIndex,
    onUsageActiveIndexChange: setUsageActiveIndex,
    usageItems,
    usageCenterLabel: usageCenter.label,
    usageCenterAmountLabel: usageCenter.amountLabel,
    averageDurationLabel,
    cadenceLabel,
    labels: {
      title: t('analytics.title'),
      distribution: t('analytics.spendingDistribution'),
      supplierDistribution: t('analytics.supplierDistribution'),
      supplierEmpty: t('analytics.supplierEmpty'),
      total: t('analytics.total'),
      vat: t('analytics.vatDeduction'),
      usage: t('analytics.usageDistribution'),
      metrics: t('analytics.metrics'),
      averageDuration: t('analytics.averageDuration'),
      estimatedCadence: data === null
        ? t('analytics.estimatedCadence')
        : t('analytics.estimatedCadenceWorkers', { workers: data.processing.workers }),
      empty: t('analytics.empty'),
      vatEmpty: t('analytics.vatEmpty'),
      usageEmpty: t('analytics.usageEmpty'),
      failed: t('invoices.requestFailed'),
      retry: t('invoices.retry'),
    },
  }
}
