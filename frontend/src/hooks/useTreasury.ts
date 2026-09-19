import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { fetchTreasury, type TreasuryReport } from '@/api/treasury'
import { invoicePath, followLink } from '@/hooks/useAppRoute'
import { buildCalendarDays, calendarMonthDate, currentCalendarMonth, localDateKey, moveCalendarMonth } from '@/hooks/treasuryCalendar'

const currency = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })
const calendarDate = new Intl.DateTimeFormat('es-ES')
const calendarMonth = new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric' })

export function useTreasury() {
  const { t } = useTranslation()
  const [report, setReport] = useState<TreasuryReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [visibleMonth, setVisibleMonth] = useState(currentCalendarMonth)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const activeRequest = useRef<AbortController | null>(null)
  const load = useCallback(() => {
    if (activeRequest.current !== null) activeRequest.current.abort()
    const controller = new AbortController()
    activeRequest.current = controller
    setLoading(true)
    setFailed(false)
    void fetchTreasury(controller.signal).then(result => {
      if (!controller.signal.aborted) setReport(result)
    }).catch(() => {
      if (!controller.signal.aborted) setFailed(true)
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
  }, [])
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    load()
    return () => {
      if (activeRequest.current !== null) activeRequest.current.abort()
      activeRequest.current = null
    }
  }, [load])

  const summary = report === null ? [] : [
    { id: 'next-7-days', label: t('treasury.next7Days'), value: currency.format(Number(report.summary.next_7_days)), subtitle: t('treasury.next7DaysSubtitle') },
    { id: 'next-30-days', label: t('treasury.next30Days'), value: currency.format(Number(report.summary.next_30_days)), subtitle: t('treasury.next30DaysSubtitle') },
    { id: 'blocked', label: t('treasury.blocked'), value: currency.format(Number(report.summary.blocked_in_review)), subtitle: t('treasury.blockedSubtitle') },
  ]
  const rows = report === null ? [] : report.by_supplier.map(supplier => ({
    ...supplier,
    displayAmount: currency.format(Number(supplier.committed_amount)),
    displayDueDate: calendarDate.format(new Date(`${supplier.next_due_date}T00:00:00`)),
  }))
  const payments = report === null ? [] : report.payments.map(payment => ({
    ...payment,
    href: invoicePath(payment.document_id),
    displayAmount: currency.format(Number(payment.amount)),
  }))
  const calendarDays = buildCalendarDays(visibleMonth, report === null ? [] : report.payments, selectedDate, localDateKey(new Date())).map(day => (
    day === null ? null : {
      ...day,
      displayAmount: currency.format(day.amount),
      ariaLabel: t('treasury.calendar.dayLabel', { date: calendarDate.format(new Date(`${day.date}T00:00:00`)), count: day.invoiceCount }),
    }
  ))
  const selectedPayments = selectedDate === null ? [] : payments.filter(payment => payment.due_date === selectedDate)
  const showPreviousMonth = () => {
    setVisibleMonth(month => moveCalendarMonth(month, -1))
    setSelectedDate(null)
  }
  const showNextMonth = () => {
    setVisibleMonth(month => moveCalendarMonth(month, 1))
    setSelectedDate(null)
  }

  return {
    mount, loading, failed, summary, rows, onRetry: load, onDocumentLink: followLink,
    calendar: {
      month: calendarMonth.format(calendarMonthDate(visibleMonth)),
      days: calendarDays,
      selectedDate: selectedDate === null ? null : calendarDate.format(new Date(`${selectedDate}T00:00:00`)),
      selectedPayments,
      hasPayments: calendarDays.some(day => day !== null && day.invoiceCount > 0),
      onPreviousMonth: showPreviousMonth,
      onNextMonth: showNextMonth,
      onSelectDate: setSelectedDate,
    },
    labels: {
      title: t('treasury.title'), supplier: t('treasury.supplier'),
      approvedInvoices: t('treasury.approvedInvoices'), committedAmount: t('treasury.committedAmount'),
      nextDueDate: t('treasury.nextDueDate'), empty: t('treasury.empty'),
      failed: t('invoices.requestFailed'), retry: t('treasury.retry'),
      calendarTitle: t('treasury.calendar.title'), previousMonth: t('treasury.calendar.previousMonth'),
      nextMonth: t('treasury.calendar.nextMonth'), paymentLimit: t('treasury.calendar.paymentLimit'),
      noPaymentsThisMonth: t('treasury.calendar.noPaymentsThisMonth'),
      selectPaymentDate: t('treasury.calendar.selectPaymentDate'),
      selectedDateTitle: (date: string) => t('treasury.calendar.selectedDateTitle', { date }),
      openInvoice: t('treasury.calendar.openInvoice'),
      weekdays: [
        t('treasury.calendar.monday'), t('treasury.calendar.tuesday'), t('treasury.calendar.wednesday'),
        t('treasury.calendar.thursday'), t('treasury.calendar.friday'), t('treasury.calendar.saturday'),
        t('treasury.calendar.sunday'),
      ],
    },
  }
}
