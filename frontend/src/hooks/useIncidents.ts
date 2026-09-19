import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { fetchInvoiceIncidents, type InvoiceIncident } from '@/api/invoices'
import { followLink, invoicePath } from '@/hooks/useAppRoute'
import { useTableSort } from '@/hooks/useTableSort'

export type IncidentSortColumn = 'issued' | 'created' | 'due'

const currency = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })
const calendarDate = new Intl.DateTimeFormat('es-ES')
const dateValue = (value: string | null): number | null => value === null ? null : Date.parse(value)

export function useIncidents() {
  const { t } = useTranslation()
  const [incidents, setIncidents] = useState<InvoiceIncident[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const activeRequest = useRef<AbortController | null>(null)
  const { sortColumn, sortDirection, onToggleSort, sortRows } = useTableSort<IncidentSortColumn>()

  const load = useCallback(() => {
    if (activeRequest.current !== null) activeRequest.current.abort()
    const controller = new AbortController()
    activeRequest.current = controller
    setLoading(true)
    setFailed(false)
    void fetchInvoiceIncidents(controller.signal).then(result => {
      if (!controller.signal.aborted) setIncidents(result)
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

  const rows = sortRows(incidents, (incident, column) => {
    if (column === 'issued') return dateValue(incident.invoice_date)
    if (column === 'created') return dateValue(incident.created_at)
    return dateValue(incident.due_date)
  }).map(incident => ({
    ...incident,
    href: invoicePath(incident.invoice_id),
    issuedLabel: incident.invoice_date === null ? t('extraction.unavailable') : calendarDate.format(new Date(`${incident.invoice_date}T00:00:00`)),
    createdLabel: calendarDate.format(new Date(incident.created_at)),
    dueLabel: incident.due_date === null ? t('extraction.unavailable') : calendarDate.format(new Date(`${incident.due_date}T00:00:00`)),
    amountLabel: incident.amount_eur === null ? t('extraction.unavailable') : currency.format(Number(incident.amount_eur)),
    failures: incident.failures.map((failure, index) => ({
      key: `${failure.rule}-${index}`,
      // Decisions published before rules were paired with their reason keep the full sentence.
      label: failure.rule === '' ? failure.reason : t(`incidents.rules.${failure.rule}`, { defaultValue: failure.rule }),
      reason: failure.reason,
    })),
  }))

  return {
    mount, loading, failed, rows, sortColumn, sortDirection, onToggleSort,
    onRetry: load, onInvoiceLink: followLink,
    labels: {
      title: t('incidents.title'), subtitle: t('incidents.subtitle'), invoice: t('incidents.invoice'),
      issuedDate: t('incidents.issuedDate'), createdDate: t('incidents.createdDate'), dueDate: t('incidents.dueDate'),
      amount: t('incidents.amount'), reasons: t('incidents.reasons'), empty: t('incidents.empty'),
      failed: t('invoices.requestFailed'), retry: t('incidents.retry'), openInvoice: t('incidents.openInvoice'),
    },
  }
}
