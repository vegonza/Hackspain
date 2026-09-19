import { useCallback, useRef, useState, type ChangeEvent, type CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

import { exportAccounting, fetchAccounting, type AccountingReport, type ExpenseCategory, type ReviewReason } from '@/api/accounting'
import { invoicePath, followLink } from '@/hooks/useAppRoute'

const currency = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })
const calendarDate = new Intl.DateTimeFormat('es-ES')

export function useAccounting() {
  const { t } = useTranslation()
  const currentYear = new Date().getFullYear()
  const [year, setYear] = useState(currentYear)
  const [quarter, setQuarter] = useState<number | null>(null)
  const [report, setReport] = useState<AccountingReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [exporting, setExporting] = useState(false)
  const activeRequest = useRef<AbortController | null>(null)
  const load = useCallback(() => {
    if (activeRequest.current !== null) activeRequest.current.abort()
    const controller = new AbortController()
    activeRequest.current = controller
    setLoading(true)
    setFailed(false)
    void fetchAccounting(year, quarter, controller.signal).then(result => {
      if (!controller.signal.aborted) setReport(result)
    }).catch(() => {
      if (!controller.signal.aborted) setFailed(true)
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
  }, [quarter, year])
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    load()
    return () => {
      if (activeRequest.current !== null) activeRequest.current.abort()
      activeRequest.current = null
    }
  }, [load])
  const categoryLabels: Record<ExpenseCategory, string> = {
    supplies: t('accounting.categories.supplies'),
    professional_services: t('accounting.categories.professionalServices'),
    rent: t('accounting.categories.rent'),
    repairs: t('accounting.categories.repairs'),
    insurance: t('accounting.categories.insurance'),
    banking: t('accounting.categories.banking'),
    advertising: t('accounting.categories.advertising'),
    utilities: t('accounting.categories.utilities'),
    travel: t('accounting.categories.travel'),
    meals: t('accounting.categories.meals'),
    vehicle: t('accounting.categories.vehicle'),
    other: t('accounting.categories.other'),
  }
  const reasonLabels: Record<ReviewReason, string> = {
    missing_payment_decision: t('accounting.reasons.missingPaymentDecision'),
    payment_review: t('accounting.reasons.paymentReview'),
    missing_identity: t('accounting.reasons.missingIdentity'),
    invalid_date: t('accounting.reasons.invalidDate'),
    missing_amounts: t('accounting.reasons.missingAmounts'),
    invalid_tax_amounts: t('accounting.reasons.invalidTaxAmounts'),
    sensitive_category: t('accounting.reasons.sensitiveCategory'),
    unknown_category: t('accounting.reasons.unknownCategory'),
  }
  const summary = report === null ? [] : [
    { id: 'recorded', label: t('accounting.recordedExpenses'), value: currency.format(Number(report.summary.recorded_expenses)), subtitle: t('accounting.recordedExpensesSubtitle'), tone: 'neutral' },
    { id: 'deductible-expenses', label: t('accounting.potentialExpenses'), value: currency.format(Number(report.summary.potential_deductible_expenses)), subtitle: t('accounting.potentialExpensesSubtitle'), tone: 'positive' },
    { id: 'deductible-vat', label: t('accounting.potentialVat'), value: currency.format(Number(report.summary.potential_deductible_vat)), subtitle: t('accounting.potentialVatSubtitle'), tone: 'primary' },
    { id: 'review', label: t('accounting.underReview'), value: currency.format(Number(report.summary.amount_under_review)), subtitle: t('accounting.underReviewSubtitle', { count: report.summary.review_invoices }), tone: 'warning' },
  ]
  const categoryTotal = report === null ? 0 : report.by_category.reduce((total, item) => total + Number(item.tax_base), 0)
  const categories = report === null ? [] : report.by_category.map(item => {
    const share = categoryTotal === 0 ? 0 : Number(item.tax_base) / categoryTotal * 100
    return {
      ...item,
      label: categoryLabels[item.category],
      displayBase: currency.format(Number(item.tax_base)),
      displayVat: currency.format(Number(item.vat_amount)),
      displayShare: t('accounting.categoryShare', { value: share.toLocaleString('es-ES', { maximumFractionDigits: 1 }) }),
      displayInvoices: t('accounting.invoiceCountValue', { count: item.invoice_count }),
      displayReview: t('accounting.reviewCountValue', { count: item.review_count }),
      barStyle: { '--accounting-bar-width': `${share}%` } as CSSProperties,
    }
  })
  const invoices = report === null ? [] : report.invoices.map(invoice => ({
    ...invoice,
    href: invoicePath(invoice.document_id),
    displayDate: invoice.invoice_date === null ? t('extraction.unavailable') : calendarDate.format(new Date(`${invoice.invoice_date}T00:00:00`)),
    displaySupplier: invoice.supplier_name === null ? t('extraction.unavailable') : invoice.supplier_name,
    displayCategory: categoryLabels[invoice.category],
    displayBase: invoice.tax_base === null ? t('extraction.unavailable') : currency.format(Number(invoice.tax_base)),
    displayVat: invoice.vat_amount === null ? t('extraction.unavailable') : currency.format(Number(invoice.vat_amount)),
    displayReasons: invoice.review_reasons.map(reason => reasonLabels[reason]).join(' · '),
    displayStatus: invoice.status === 'PREPARED' ? t('accounting.prepared') : t('accounting.review'),
  }))
  const periods = [
    { id: 'annual', label: t('accounting.annual'), active: quarter === null, onSelect: () => setQuarter(null) },
    ...[1, 2, 3, 4].map(value => ({
      id: `quarter-${value}`, label: t('accounting.quarter', { value }), active: quarter === value,
      onSelect: () => setQuarter(value),
    })),
  ]
  const years = [currentYear - 2, currentYear - 1, currentYear]
  const readiness = report === null ? null : (() => {
    const total = report.summary.prepared_invoices + report.summary.review_invoices
    const rate = total === 0 ? 0 : Math.round(report.summary.prepared_invoices / total * 100)
    return {
      rate,
      displayRate: t('accounting.preparedPercent', { value: rate }),
      description: t('accounting.readinessDescription', { prepared: report.summary.prepared_invoices, total }),
      prepared: report.summary.prepared_invoices,
      review: report.summary.review_invoices,
      progressStyle: { '--accounting-progress': `${rate * 3.6}deg` } as CSSProperties,
    }
  })()
  const selectedPeriod = `${year} · ${quarter === null ? t('accounting.annual') : t('accounting.quarter', { value: quarter })}`
  const onYearChange = (event: ChangeEvent<HTMLSelectElement>) => setYear(Number(event.target.value))
  const onExport = () => {
    setExporting(true)
    void exportAccounting(year, quarter).then(blob => {
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `precierre-fiscal-${year}${quarter === null ? '' : `-t${quarter}`}.csv`
      anchor.click()
      URL.revokeObjectURL(url)
      toast.success(t('accounting.exported'))
    }).catch(() => undefined).finally(() => setExporting(false))
  }

  return {
    mount, loading, failed, exporting, summary, categories, invoices, periods, years, year, readiness, selectedPeriod,
    onYearChange, onExport, onRetry: load, onDocumentLink: followLink,
    labels: {
      title: t('accounting.title'), subtitle: t('accounting.subtitle'), advisory: t('accounting.advisory'),
      controlCenter: t('accounting.controlCenter'), period: t('accounting.period'), overview: t('accounting.overview'),
      readiness: t('accounting.readiness'), ready: t('accounting.ready'), pending: t('accounting.pending'),
      categoriesSubtitle: t('accounting.categoriesSubtitle'), invoicesSubtitle: t('accounting.invoicesSubtitle'),
      invoiceTotal: t('accounting.invoiceTotal', { count: invoices.length }), vatShort: t('accounting.vatShort'),
      export: t('accounting.export'), exporting: t('accounting.exporting'), categories: t('accounting.categoryBreakdown'),
      category: t('accounting.category'), invoices: t('accounting.invoices'), invoice: t('accounting.invoice'),
      supplier: t('accounting.supplier'), date: t('accounting.date'), account: t('accounting.account'),
      taxBase: t('accounting.taxBase'), vat: t('accounting.vat'), status: t('accounting.status'),
      reasons: t('accounting.reasonsTitle'), invoiceCount: t('accounting.invoiceCount'),
      reviewCount: t('accounting.reviewCount'), empty: t('accounting.empty'),
      failed: t('invoices.requestFailed'), retry: t('accounting.retry'), openInvoice: t('accounting.openInvoice'),
    },
  }
}
