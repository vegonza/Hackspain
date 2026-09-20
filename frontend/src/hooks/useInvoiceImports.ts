import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Invoice } from '@/api/invoices'
import { invoiceErrorKey } from '@/hooks/invoiceError'
import { invoicePath } from '@/hooks/useAppRoute'

export interface InvoiceUpload {
  id: string
  name: string
  file: File
  status: 'queued' | 'uploading' | 'error'
}

export function useInvoiceImports(invoices: Invoice[], uploads: InvoiceUpload[], isInvoiceList: boolean) {
  const { t } = useTranslation()
  const [trackedIds, setTrackedIds] = useState<ReadonlySet<string>>(() => new Set())
  const [dismissed, setDismissed] = useState(false)
  const incoming = invoices.filter(invoice => invoice.status !== 'ready' && !trackedIds.has(invoice.id))
  const ids = incoming.length === 0 ? trackedIds : new Set([...trackedIds, ...incoming.map(invoice => invoice.id)])
  if (ids !== trackedIds) setTrackedIds(ids)
  const tracked = invoices.filter(invoice => ids.has(invoice.id))
  const rows = [
    ...uploads.map(upload => ({
      id: upload.id, name: upload.name, status: upload.status, href: null,
      statusLabel: t(`invoices.${upload.status}`),
      description: upload.status === 'error' ? t('imports.uploadFailed') : t(`invoices.${upload.status}`),
      retryLabel: t('invoices.retry'), retryConfirmation: t('imports.retryUpload', { name: upload.name }),
    })),
    ...tracked.map(invoice => ({
      id: invoice.id, name: invoice.name, status: invoice.status, href: invoicePath(invoice.id),
      statusLabel: invoice.status === 'ready' ? t('imports.completed')
        : invoice.next_retry_at !== null ? t('invoices.retryQueued') : t(`invoices.${invoice.status}`),
      description: invoice.status === 'error' ? t(invoiceErrorKey(invoice.last_error))
        : invoice.status === 'ready' ? t('imports.completed') : t(`invoices.${invoice.status}`),
      retryLabel: t('invoices.redo'), retryConfirmation: t('invoices.redoConfirmation', { name: invoice.name }),
    })),
  ]
  const completed = rows.filter(row => row.status === 'ready').length
  const errors = rows.filter(row => row.status === 'error').length
  const total = rows.length
  const active = total - completed - errors
  if (dismissed && (active > 0 || incoming.length > 0)) setDismissed(false)

  return {
    visible: isInvoiceList && !dismissed && total > 0, rows, completed, total,
    canDismiss: active === 0,
    closeLabel: t('common.close'),
    onDismiss: () => { if (active === 0) setDismissed(true) },
    summary: t('imports.progress', { completed, total }),
    track: (id: string) => { setTrackedIds(current => new Set([...current, id])); setDismissed(false) },
  }
}
