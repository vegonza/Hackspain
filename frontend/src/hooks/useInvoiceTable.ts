import { useCallback, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { downloadInvoice } from '@/api/invoices'
import { invoiceErrorKey } from '@/hooks/invoiceError'
import { invoicePath } from '@/hooks/useAppRoute'
import { useMonthShortcuts } from '@/hooks/useMonthShortcuts'
import { formatAmount, formatStatus } from '@/lib/format'
import { supplierLogo } from '@/lib/supplierLogos'
import { billingDecision, euroTotal, invoiceDate, matchesInvoice, periodInvoices, shiftMonth, sortInvoices,
  type BillingInvoice, type BillingSort } from '@/hooks/invoiceBilling'

export function useInvoiceTable(invoices: BillingInvoice[], loading: boolean) {
  const { t } = useTranslation()
  const now = new Date()
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  const [period, setPeriod] = useState(currentMonth)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<{ column: BillingSort; direction: 'asc' | 'desc' }>({ column: 'date', direction: 'desc' })
  const [downloading, setDownloading] = useState<string | null>(null)
  const downloadInFlight = useRef(false)
  const canNavigateMonths = period !== 'all' && period !== 'undated'
  const canNextMonth = canNavigateMonths && period < currentMonth
  const onMoveMonth = useCallback((direction: -1 | 1): void => {
    setPeriod(current => {
      if (current === 'all' || current === 'undated') return current
      const next = shiftMonth(current, direction)
      return next <= currentMonth ? next : current
    })
  }, [currentMonth])
  const mountMonthShortcuts = useMonthShortcuts(loading || !canNavigateMonths, onMoveMonth)
  const monthLabel = (month: string): string => formatStatus(new Date(`${month}-01T12:00:00`).toLocaleDateString('es-ES', { month: 'long', year: 'numeric' }))
  const { months, undatedCount } = useMemo(() => {
    const counts = new Map<string, number>([[currentMonth, 0]])
    if (period !== 'all' && period !== 'undated') counts.set(period, 0)
    let undatedCount = 0
    for (const invoice of invoices) {
      const date = invoiceDate(invoice)
      if (date === null) {
        undatedCount++
        continue
      }
      const month = date.slice(0, 7)
      if (month > currentMonth) continue
      if (!counts.has(month)) counts.set(month, 0)
      counts.set(month, counts.get(month)! + 1)
    }
    return { months: [...counts].sort(([left], [right]) => right.localeCompare(left))
      .map(([value, count]) => ({ value, count })), undatedCount }
  }, [invoices, period, currentMonth])
  const inPeriod = useMemo(() => periodInvoices(invoices, period), [invoices, period])
  const filtered = sortInvoices(inPeriod.filter(invoice => matchesInvoice(invoice, search)), sort.column, sort.direction)
  const summaries = (['all', 'PAGAR', 'ESCALAR'] as const).map(value => {
    const total = euroTotal(value === 'all' ? inPeriod : inPeriod.filter(invoice => billingDecision(invoice) === value))
    return { value, label: value === 'all' ? t('billing.periodTotal') : value === 'PAGAR' ? t('billing.payable') : t('billing.rowDecisions.ESCALAR'),
      amount: total.count > 0 && total.unknown === total.count ? '—' : formatAmount(total.cents / 100, 'EUR'),
      count: t('billing.invoiceCount', { count: total.count }),
      incomplete: total.unknown > 0,
      description: total.unknown > 0 ? t('billing.unknownAmounts', { count: total.unknown }) : t('billing.eurTotals'),
    }
  })
  const rows = filtered.map(invoice => {
    const data = invoice.billing
    const supplierName = data === null ? null : data.supplier_name
    const name = supplierName === null || supplierName === '' ? t('billing.unknownSupplier') : supplierName
    const initials = supplierName === null || supplierName === '' ? null : supplierName.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('').toLocaleUpperCase('es-ES')
    const number = data === null ? null : data.invoice_number
    const concept = data === null || data.line_items === null ? '' : [...new Set(data.line_items.map(line => line.description.trim()).filter(description => description !== ''))].join(' · ')
    const date = invoiceDate(invoice)
    const decision = billingDecision(invoice)
    const rowDecisionLabel = t(`billing.rowDecisions.${decision}`)
    const currency = data === null || data.currency === null ? '' : data.currency
    const gross = data === null ? '—' : data.total_eur !== null ? formatAmount(Number(data.total_eur), 'EUR')
      : data.total !== null ? formatAmount(Number(data.total), currency) : '—'
    const amount = data === null ? '—' : data.tax_base_eur !== null ? formatAmount(Number(data.tax_base_eur), 'EUR')
      : data.tax_base !== null ? formatAmount(Number(data.tax_base), currency) : '—'
    const originalAmount = data !== null && currency !== '' && currency !== 'EUR'
      ? t('billing.originalAmount', { amount: data.tax_base === null ? '—' : formatAmount(Number(data.tax_base), currency) }) : null
    const reasons = invoice.payment_decision === null ? [] : invoice.payment_decision.reasons
    const statusLabel = invoice.next_retry_at !== null ? t('invoices.retryQueued') : t(`invoices.${invoice.status}`)
    const decisionDescription = invoice.status === 'error' ? t(invoiceErrorKey(invoice.last_error))
      : invoice.status !== 'ready' ? statusLabel : reasons.length === 0 ? rowDecisionLabel : reasons.join(' · ')
    return {
      id: invoice.id, name: invoice.name, supplier: name, initials,
      logo: supplierLogo(supplierName),
      secondary: [number, invoice.name, concept].filter(value => value !== null && value !== '').join(' · '),
      date: date === null ? t('billing.undated') : new Date(`${date}T12:00:00`).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' }),
      amount, gross: t('billing.grossAmount', { amount: gross }), originalAmount,
      decision, decisionLabel: rowDecisionLabel, decisionDescription,
      classification: decision === 'paid' || decision === 'pending' ? null : decision,
      showStatus: invoice.status !== 'ready', status: invoice.status,
      statusLabel,
      href: invoicePath(invoice.id), canOpen: invoice.status !== 'uploading',
      canManage: invoice.status === 'ready' || invoice.status === 'error',
      deleteConfirmation: t('invoices.deleteConfirmation', { name: invoice.name }),
      redoConfirmation: t('invoices.redoConfirmation', { name: invoice.name }),
    }
  })
  async function download(id: string): Promise<void> {
    if (downloadInFlight.current) return
    downloadInFlight.current = true
    setDownloading(id)
    try {
      const file = await downloadInvoice(id)
      const invoice = invoices.find(invoice => invoice.id === id)!
      const url = URL.createObjectURL(file)
      const link = document.createElement('a')
      link.href = url
      link.download = invoice.name
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      // API failures are displayed by the centralized client.
    } finally {
      downloadInFlight.current = false
      setDownloading(null)
    }
  }
  return {
    rows, search, onSearch: setSearch, period,
    onPeriod: (value: string) => { if (value === 'all' || value === 'undated' || value <= currentMonth) setPeriod(value) },
    summaries, sort,
    onSort: (column: BillingSort) => setSort({ column, direction: sort.column === column && sort.direction === 'asc' ? 'desc' : 'asc' }),
    monthOptions: [{ value: 'all', label: t('billing.allMonths'), count: invoices.length },
      ...months.map(month => ({ ...month, label: monthLabel(month.value) })),
      { value: 'undated', label: t('billing.undated'), count: undatedCount }],
    canNavigateMonths, canNextMonth, mountMonthShortcuts,
    onPreviousMonth: () => onMoveMonth(-1), onNextMonth: () => onMoveMonth(1),
    downloading, onDownload: (id: string) => void download(id),
    labels: {
      title: t('invoices.library'), search: t('billing.search'), upload: t('invoices.upload'),
      downloadPdf: t('billing.downloadPdf'), delete: t('invoices.delete'), redo: t('invoices.redo'),
      period: t('billing.period'),
      previousMonth: t('billing.previousMonth'), nextMonth: t('billing.nextMonth'),
      supplier: t('billing.supplier'), review: t('billing.review'),
      date: t('billing.date'), amount: t('billing.amount'), actions: t('invoices.actions'),
    },
    emptyMessage: search.trim() !== '' ? t('invoices.noResults')
      : invoices.length === 0 ? t('invoices.emptyList') : t('billing.empty'),
  }
}
