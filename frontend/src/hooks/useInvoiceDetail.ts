import { useCallback, useRef, useState } from 'react'
import { fetchInvoice, fetchPdfUrl, type Invoice, type InvoiceDetail } from '@/api/invoices'

export type InvoiceSourceTab = 'pdf' | 'text'
export type InvoiceDataTab = 'extraction' | 'erp'

export function useInvoiceDetail(invoiceId: string | null) {
  const [sourceTab, setSourceTab] = useState<InvoiceSourceTab>('pdf')
  const [dataTab, setDataTab] = useState<InvoiceDataTab>('extraction')
  const [detail, setDetail] = useState<InvoiceDetail | null>(null)
  const [requestedId, setRequestedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const requestVersion = useRef(0)
  const detailVersion = useRef(0)
  const mountedId = useRef<string | null>(null)

  const refreshDetail = useCallback(async (): Promise<void> => {
    if (invoiceId === null || mountedId.current !== invoiceId) return
    const request = requestVersion.current
    const version = ++detailVersion.current
    try {
      const result = await fetchInvoice(invoiceId)
      if (request === requestVersion.current && version === detailVersion.current) setDetail(result)
    } finally {
      if (request === requestVersion.current && version === detailVersion.current) setLoading(false)
    }
  }, [invoiceId])

  const updateMetrics = useCallback((invoices: Invoice[]): void => {
    setDetail(current => {
      if (current === null) return null
      const summary = invoices.find(document => document.id === current.id)
      if (summary === undefined) return current
      return {
        ...current, total_cost_usd: summary.total_cost_usd, finished_at: summary.finished_at,
        total_duration_ms: summary.total_duration_ms,
      }
    })
  }, [])

  const mountDetail = useCallback((node: HTMLDivElement | null) => {
    if (node === null || invoiceId === null) return
    const request = ++requestVersion.current
    mountedId.current = invoiceId
    setRequestedId(invoiceId)
    setSourceTab('pdf')
    setDataTab('extraction')
    setDetail(null)
    setPdfUrl(null)
    setLoading(true)
    setPdfLoading(true)
    void Promise.allSettled([
      refreshDetail(),
      fetchPdfUrl(invoiceId).then(({ url }) => {
        if (request === requestVersion.current) setPdfUrl(url)
      }).finally(() => {
        if (request === requestVersion.current) setPdfLoading(false)
      }),
    ])
    return () => {
      ++requestVersion.current
      mountedId.current = null
    }
  }, [invoiceId, refreshDetail])

  return {
    sourceTab: requestedId === invoiceId ? sourceTab : 'pdf' as InvoiceSourceTab,
    dataTab: requestedId === invoiceId ? dataTab : 'extraction' as InvoiceDataTab,
    onSourceTab: (value: string): void => { if (value !== '') setSourceTab(value as InvoiceSourceTab) },
    onDataTab: (value: string): void => { if (value !== '') setDataTab(value as InvoiceDataTab) },
    selected: detail !== null && detail.id === invoiceId ? detail : null,
    loading: invoiceId !== null && (requestedId !== invoiceId || loading),
    pdfLoading: invoiceId !== null && (requestedId !== invoiceId || pdfLoading),
    pdfUrl: requestedId === invoiceId ? pdfUrl : null,
    mountDetail, refreshDetail, updateMetrics,
  }
}
