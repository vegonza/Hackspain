import { useCallback, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { gestoriaStatusBadge } from '@/hooks/gestoriaStatuses'
import { fetchGestoria, saveGestoria, sendGestoria, type GestoriaInvoice, type GestoriaStatus } from '@/api/gestoria'

export function useGestoria(period: string, periodLabel: string) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [email, setEmail] = useState('')
  const [invoices, setInvoices] = useState<GestoriaInvoice[]>([])
  const [statuses, setStatuses] = useState<GestoriaStatus[]>([])
  const inFlight = useRef(false)
  const mount = useCallback((node: HTMLFormElement | null) => {
    if (node === null) return
    const controller = new AbortController()
    setLoading(true); setFailed(false)
    void fetchGestoria(period, controller.signal).then(value => {
      if (controller.signal.aborted) return
      setEmail(value.email); setInvoices(value.invoices); setStatuses(value.statuses)
    }).catch(() => { if (!controller.signal.aborted) setFailed(true) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [period])
  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (inFlight.current || loading || failed) return
    inFlight.current = true; setBusy(true)
    try {
      await saveGestoria(email)
      if (invoices.length > 0) {
        const result = await sendGestoria(email, invoices, period)
        toast.success(t('gestoria.sent', { count: result.sent }))
      } else toast.success(t('gestoria.saved'))
      setOpen(false)
    } catch {
      // API errors are shown by the centralized client.
    } finally { inFlight.current = false; setBusy(false) }
  }
  return {
    open, mount, loading, failed, busy, email,
    onOpen: () => setOpen(true), onOpenChange: (value: boolean) => { if (!inFlight.current) setOpen(value) },
    onEmail: setEmail, onSubmit: submit,
    statuses: statuses.map(row => ({ key: `${row.kind}-${row.status}`, count: row.count, badge: gestoriaStatusBadge(row, t) })),
    labels: {
      title: t('gestoria.title'), email: t('gestoria.email'), period: periodLabel, ready: t('gestoria.ready'), empty: t('gestoria.empty'),
      submit: busy ? t('gestoria.sending') : invoices.length > 0 ? t('gestoria.send', { count: invoices.length }) : t('gestoria.save'),
      close: t('common.close'), cancel: t('common.cancel'), failed: t('invoices.requestFailed'),
    },
  }
}
