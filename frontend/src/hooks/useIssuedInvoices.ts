import { useCallback, useRef, useState } from 'react'
import { fetchIssuedInvoices, type IssuedInvoice, type IssuedInvoiceSummary } from '@/api/issued'

export function useIssuedInvoices() {
  const [invoices, setInvoices] = useState<IssuedInvoiceSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const dataRevision = useRef(0)
  const updates = useRef(new Map<string, { revision: number; invoice: IssuedInvoiceSummary }>())
  const loaded = useRef(false)
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    const controller = new AbortController()
    let fetching = false
    let retry: ReturnType<typeof setTimeout> | undefined
    async function refresh(): Promise<void> {
      if (fetching || controller.signal.aborted || document.hidden) return
      fetching = true
      clearTimeout(retry)
      const version = dataRevision.current
      setLoading(!loaded.current)
      try {
        const rows = await fetchIssuedInvoices(controller.signal)
        if (controller.signal.aborted) return
        const changed = [...updates.current.values()].filter(update => update.revision > version).map(update => update.invoice)
        setInvoices([...new Map([...rows, ...changed].map(invoice => [invoice.id, invoice])).values()])
        updates.current.clear()
        loaded.current = true
        setFailed(false)
      } catch {
        if (!controller.signal.aborted) {
          setFailed(true)
          retry = setTimeout(() => void refresh(), 5000)
        }
      } finally {
        fetching = false
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    const onVisible = (): void => { void refresh() }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)
    void refresh()
    return () => {
      controller.abort()
      clearTimeout(retry)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
    }
  }, [])
  const update = useCallback((detail: IssuedInvoice) => {
    const { id, status, invoice_number, issue_date, client, items, base_amount, total_amount, pdf_path } = detail
    const invoice: IssuedInvoiceSummary = { id, status, invoice_number, issue_date, client, items, base_amount, total_amount, pdf_path }
    dataRevision.current++
    updates.current.set(id, { revision: dataRevision.current, invoice })
    setInvoices(current => [...current.filter(row => row.id !== invoice.id), invoice])
  }, [])
  return { invoices, loading, failed, mount, update }
}
