import { invoiceErrorKey } from '@/hooks/invoiceError'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { invoicePath } from '@/hooks/useAppRoute'
import type { useInvoices } from '@/hooks/useInvoices'
import { useTablePagination } from '@/hooks/useTablePagination'
import { formatDateLong } from '@/lib/format'

type Options = Pick<ReturnType<typeof useInvoices>, 'filteredInvoices' | 'search' | 'sortColumn' | 'sortDirection'>

export function useInvoiceTable({ filteredInvoices, search, sortColumn, sortDirection }: Options) {
  const { t } = useTranslation()
  const { rows: pageRows, pagination, pageKey } = useTablePagination(filteredInvoices, JSON.stringify([search, sortColumn, sortDirection]))
  const rows = useMemo(() => {
    const formatCost = (cost: string | null): string => cost === null ? '—' : `$${Number(cost).toFixed(4)}`
    const formatDuration = (duration: number | null): string => {
      if (duration === null) return '—'
      const centiseconds = Math.round(duration / 10)
      return centiseconds < 6000
        ? t('processing.durationSeconds', { value: (centiseconds / 100).toFixed(2) })
        : t('processing.durationMinutes', { minutes: Math.floor(centiseconds / 6000), seconds: ((centiseconds % 6000) / 100).toFixed(2) })
    }
    return pageRows.map(document => ({
      ...document,
      decisionLabel: document.payment_decision === null ? t('invoices.decisionPending') : t(`invoices.decisions.${document.payment_decision.classification}`),
      costLabel: formatCost(document.total_cost_usd),
      href: invoicePath(document.id),
      durationLabel: formatDuration(document.total_duration_ms),
      canOpen: document.status !== 'uploading',
      canDelete: document.status === 'ready' || document.status === 'error',
      canRedo: document.status === 'ready' || document.status === 'error',
      statusIcon: document.status === 'uploading' || document.status === 'processing' ? 'spinner'
        : document.status === 'queued' ? 'clock' : document.status === 'error' ? 'error' : null,
      statusLabel: document.next_retry_at !== null ? t('invoices.retryQueued') : t(`invoices.${document.status}`),
      deleteConfirmation: t('invoices.deleteConfirmation', { name: document.name }),
      redoConfirmation: t('invoices.redoConfirmation', { name: document.name }),
      dateLabel: document.status === 'uploading' ? '—' : formatDateLong(document.created_at, 'es-ES'),
      errorMessage: document.status === 'error' ? t(invoiceErrorKey(document.last_error)) : '',
    }))
  }, [pageRows, t])
  return { rows, pagination, pageKey }
}
