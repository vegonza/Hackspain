import { useCallback, useRef, useState } from 'react'
import { fetchInvoice, fetchPdfUrl, type Invoice, type InvoiceDetail, type StageId } from '@/api/invoices'

export type InvoiceTab = 'pdf' | 'erp' | StageId

export function useInvoiceDetail(invoiceId: string | null) {
  const [sourceTab, setSourceTab] = useState<InvoiceTab>('pdf')
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
      const summary = invoices.find(invoice => invoice.id === current.id)
      if (summary === undefined) return current
      return {
        ...current, total_cost_usd: summary.total_cost_usd, finished_at: summary.finished_at,
        stage_metrics: summary.stage_metrics,
        stages: current.stages.map(stage => {
          const metric = summary.stage_metrics.find(item => item.stage === stage.id)
          return metric === undefined ? stage : { ...stage, cost_usd: metric.cost_usd, duration_ms: metric.duration_ms }
        }),
      }
    })
  }, [])

  const mountDetail = useCallback((node: HTMLDivElement | null) => {
    if (node === null || invoiceId === null) return
    const request = ++requestVersion.current
    mountedId.current = invoiceId
    setRequestedId(invoiceId)
    setSourceTab('pdf')
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
    sourceTab: requestedId === invoiceId ? sourceTab : 'pdf' as InvoiceTab,
    onSourceTab: setSourceTab,
    selected: detail !== null && detail.id === invoiceId ? detail : null,
    loading: invoiceId !== null && (requestedId !== invoiceId || loading),
    pdfLoading: invoiceId !== null && (requestedId !== invoiceId || pdfLoading),
    pdfUrl: requestedId === invoiceId ? pdfUrl : null,
    mountDetail, refreshDetail, updateMetrics,
  }
}
