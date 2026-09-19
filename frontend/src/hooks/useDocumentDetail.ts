import { useCallback, useRef, useState } from 'react'
import { fetchDocument, fetchPdfUrl, type Document, type DocumentDetail, type StageId } from '@/api/documents'

export type DocumentTab = 'pdf' | 'erp' | StageId

export function useDocumentDetail(documentId: string | null) {
  const [sourceTab, setSourceTab] = useState<DocumentTab>('pdf')
  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [requestedId, setRequestedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const requestVersion = useRef(0)
  const detailVersion = useRef(0)
  const mountedId = useRef<string | null>(null)

  const refreshDetail = useCallback(async (): Promise<void> => {
    if (documentId === null || mountedId.current !== documentId) return
    const request = requestVersion.current
    const version = ++detailVersion.current
    try {
      const result = await fetchDocument(documentId)
      if (request === requestVersion.current && version === detailVersion.current) setDetail(result)
    } finally {
      if (request === requestVersion.current && version === detailVersion.current) setLoading(false)
    }
  }, [documentId])

  const updateMetrics = useCallback((documents: Document[]): void => {
    setDetail(current => {
      if (current === null) return null
      const summary = documents.find(document => document.id === current.id)
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
    if (node === null || documentId === null) return
    const request = ++requestVersion.current
    mountedId.current = documentId
    setRequestedId(documentId)
    setSourceTab('pdf')
    setDetail(null)
    setPdfUrl(null)
    setLoading(true)
    setPdfLoading(true)
    void Promise.allSettled([
      refreshDetail(),
      fetchPdfUrl(documentId).then(({ url }) => {
        if (request === requestVersion.current) setPdfUrl(url)
      }).finally(() => {
        if (request === requestVersion.current) setPdfLoading(false)
      }),
    ])
    return () => {
      ++requestVersion.current
      mountedId.current = null
    }
  }, [documentId, refreshDetail])

  return {
    sourceTab: requestedId === documentId ? sourceTab : 'pdf' as DocumentTab,
    onSourceTab: setSourceTab,
    selected: detail !== null && detail.id === documentId ? detail : null,
    loading: documentId !== null && (requestedId !== documentId || loading),
    pdfLoading: documentId !== null && (requestedId !== documentId || pdfLoading),
    pdfUrl: requestedId === documentId ? pdfUrl : null,
    mountDetail, refreshDetail, updateMetrics,
  }
}
