import { useCallback, useRef, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateLong } from '@/lib/format'
import { toast } from 'sonner'
import { deleteDocument, retryDocument, fetchDocument, fetchDocuments, fetchPdfUrl, uploadDocument, type Document, type DocumentDetail, type StageId } from '@/api/documents'

const isProcessing = (document: Document) => document.status === 'queued' || document.status === 'processing'

interface UploadingFile { id: string; name: string }

export function useDocuments(initialDocuments: Document[]) {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [view, setView] = useState<'documents' | 'usage'>('documents')
  const [documents, setDocuments] = useState(initialDocuments)
  const [uploads, setUploads] = useState<UploadingFile[]>([])
  const [selected, setSelected] = useState<DocumentDetail | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [sourceTab, setSourceTab] = useState<'pdf' | StageId>('pdf')
  const selectionRequest = useRef(0)
  const activeId = useRef<string | null>(null)
  const documentsRef = useRef(initialDocuments)
  const listRevision = useRef(0)

  const updateDocuments = useCallback((next: Document[]) => {
    documentsRef.current = next
    setDocuments(next)
  }, [])

  const selectDocument = useCallback(async (id: string): Promise<void> => {
    if (id.startsWith('upload-')) return
    const request = ++selectionRequest.current
    activeId.current = id
    setSelectedId(id)
    setSourceTab('pdf')
    setSelected(null)
    setPdfUrl(null)
    setPdfLoading(false)
    setLoading(true)
    setPdfLoading(true)
    await Promise.allSettled([
      fetchDocument(id).then(document => {
        if (request === selectionRequest.current) setSelected(document)
      }).finally(() => {
        if (request === selectionRequest.current) setLoading(false)
      }),
      fetchPdfUrl(id).then(({ url }) => {
        if (request === selectionRequest.current) setPdfUrl(url)
      }).finally(() => {
        if (request === selectionRequest.current) setPdfLoading(false)
      }),
    ])
  }, [])

  const watchDocuments = useCallback((node: HTMLDivElement | null) => {
    if (node === null || view !== 'documents') return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function poll(): Promise<void> {
      try {
        if (!document.hidden && documentsRef.current.some(isProcessing)) {
          const revision = listRevision.current
          const next = await fetchDocuments()
          if (!active) return
          if (revision === listRevision.current) {
            const previous = documentsRef.current
            updateDocuments(next)
            setSelected(current => {
              if (current === null) return null
              const summary = next.find(document => document.id === current.id)
              if (summary === undefined) return current
              return {
                ...current,
                total_cost_usd: summary.total_cost_usd,
                total_duration_ms: summary.total_duration_ms,
                stage_metrics: summary.stage_metrics,
                stages: current.stages.map(stage => {
                  const metric = summary.stage_metrics.find(item => item.stage === stage.id)
                  return metric === undefined || metric.cost_usd === null ? stage : { ...stage, cost_usd: metric.cost_usd }
                }),
              }
            })
            for (const document of next) {
              const old = previous.find(item => item.id === document.id)
              if (old && old.status !== document.status && document.status === 'error') {
                toast.error(t('documents.processingFailed', { name: document.name }))
              }
            }
            const id = activeId.current
            const request = selectionRequest.current
            const wasProcessing = previous.some(document => document.id === id && (document.status === 'queued' || document.status === 'processing'))
            if (id !== null && wasProcessing) {
              const detail = await fetchDocument(id)
              if (active && request === selectionRequest.current && revision === listRevision.current) setSelected(detail)
            }
          }
        }
      } catch {
        // The API client displays polling errors.
      } finally {
        if (active) timer = setTimeout(() => void poll(), 3000)
      }
    }
    void poll()
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [t, updateDocuments, view])

  function onBack(): void {
    ++selectionRequest.current
    activeId.current = null
    setSelectedId(null)
    setSelected(null)
    setPdfUrl(null)
    setLoading(false)
    setPdfLoading(false)
    setView('documents')
  }

  async function onUpload(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const files = Array.from(event.target.files || [])
    event.target.value = ''
    if (files.length === 0) return
    const valid = files.filter(file => file.name.toLowerCase().endsWith('.pdf'))
    if (valid.length !== files.length) toast.error(t('documents.invalidPdf'))
    if (valid.length === 0) return
    setView('documents')
    const pending = valid.map(file => ({ id: `upload-${crypto.randomUUID()}`, name: file.name, file }))
    setUploads(current => [...pending, ...current])
    onBack()
    setSearch('')
    const tasks = pending.values()
    async function transfer(): Promise<void> {
      for (const item of tasks) {
        try {
          const document = await uploadDocument(item.file)
          ++listRevision.current
          updateDocuments([document, ...documentsRef.current.filter(existing => existing.id !== document.id)])
        } catch {
          // The API client displays upload errors.
        } finally {
          setUploads(current => current.filter(upload => upload.id !== item.id))
        }
      }
    }
    await Promise.all(Array.from({ length: Math.min(3, pending.length) }, () => transfer()))
  }

  async function onDelete(id: string): Promise<void> {
    if (deleting) return
    setDeleting(true)
    ++listRevision.current
    try {
      await deleteDocument(id)
      ++listRevision.current
      updateDocuments(documentsRef.current.filter(document => document.id !== id))
      if (activeId.current === id) {
        ++selectionRequest.current
        activeId.current = null
        setSelected(null)
        setSelectedId(null)
        setLoading(false)
      }
    } catch {
      // The API client displays the error.
    } finally {
      setDeleting(false)
    }
  }

  async function onRetry(id: string): Promise<void> {
    if (retrying) return
    setRetrying(true)
    ++listRevision.current
    try {
      const document = await retryDocument(id)
      ++listRevision.current
      updateDocuments(documentsRef.current.map(item => item.id === id ? document : item))
      const request = selectionRequest.current
      const detail = await fetchDocument(id)
      if (activeId.current === id && request === selectionRequest.current) setSelected(detail)
    } catch {
      // The API client displays the error.
    } finally {
      setRetrying(false)
    }
  }

  const formatCost = (cost: string | null): string => cost === null ? '—' : `$${Number(cost).toFixed(4)}`
  const formatDuration = (duration: number | null): string => duration === null ? '—'
    : duration < 1000 ? t('pipeline.durationMilliseconds', { value: duration })
    : duration < 60000 ? t('pipeline.durationSeconds', { value: (duration / 1000).toFixed(1) })
    : t('pipeline.durationMinutes', { minutes: Math.floor(duration / 60000), seconds: Math.floor(duration % 60000 / 1000) })
  const rows = [
    ...uploads.map(upload => ({ ...upload, status: 'uploading' as const, total_cost_usd: null, total_duration_ms: null, stage_metrics: [], current_stages: [] })),
    ...documents,
  ].map(document => ({
    ...document,
    costLabel: formatCost(document.total_cost_usd),
    durationLabel: formatDuration(document.total_duration_ms),
    costBreakdown: document.stage_metrics.map(metric => ({ label: t(`pipeline.stages.${metric.stage}`), value: formatCost(metric.cost_usd) })),
    durationBreakdown: document.stage_metrics.map(metric => ({ label: t(`pipeline.stages.${metric.stage}`), value: formatDuration(metric.duration_ms) })),
    canOpen: document.status !== 'uploading',
    canDelete: (document.status === 'ready' || document.status === 'error'),
    statusIcon: document.status === 'uploading' || document.status === 'processing' ? 'spinner'
      : document.status === 'queued' ? 'clock' : document.status === 'error' ? 'error' : null,
    statusLabel: document.status !== 'uploading' && document.next_retry_at !== null
      ? t('documents.retryQueued') : t(`documents.${document.status}`),
    deleteConfirmation: t('documents.deleteConfirmation', { name: document.name }),
    dateLabel: document.status === 'uploading' ? '—' : formatDateLong(document.created_at, 'es-ES'),
    errorMessage: document.status === 'error' ? t('documents.error') : '',
  }))

  const stages = selected === null ? [] : selected.stages.map(stage => ({
    ...stage,
    label: t(`pipeline.stages.${stage.id}`),
    statusLabel: t(`pipeline.status.${stage.status}`),
    description: t(`pipeline.description.${stage.id}`),
    costLabel: stage.cost_usd === null ? null : `$${new Intl.NumberFormat('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(Number(stage.cost_usd))}`,
    durationLabel: stage.duration_ms === null ? null : stage.duration_ms < 1000
      ? t('pipeline.durationMilliseconds', { value: stage.duration_ms })
      : stage.duration_ms < 60000
        ? t('pipeline.durationSeconds', { value: (stage.duration_ms / 1000).toFixed(1) })
        : t('pipeline.durationMinutes', { minutes: Math.floor(stage.duration_ms / 60000), seconds: Math.floor(stage.duration_ms % 60000 / 1000) }),
  }))
  const erp = selected === null ? null : selected.erp
  const erpMoney = (value: number) => `${new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)} €`
  const difference = erp !== null && selected !== null && selected.features !== null
    ? Number(selected.features.total) - Number(erp.expected_amount) : null
  const erpRows = [
    { label: t('erp.status'), value: erp === null ? '—' : t(`erp.states.${erp.status}`) },
    { label: t('erp.expectedAmount'), value: erp === null ? '—' : erpMoney(Number(erp.expected_amount)) },
    { label: t('erp.difference'), value: difference === null ? '—' : erpMoney(difference) },
    { label: t('erp.entry'), value: erp === null ? '—' : erp.entry_id },
    { label: t('erp.purchaseOrder'), value: erp === null ? '—' : erp.purchase_order },
    { label: t('erp.supplier'), value: erp === null ? '—' : erp.supplier_id },
    { label: t('erp.nif'), value: erp === null ? '—' : erp.nif },
    { label: t('erp.registeredAt'), value: erp === null ? '—' : new Date(`${erp.registered_at}T00:00:00`).toLocaleDateString('es-ES') },
  ]
  const knownCosts = stages.filter(stage => stage.cost_usd !== null)
  const totalCost = knownCosts.length === 0 ? '—' : `$${new Intl.NumberFormat('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(knownCosts.reduce((sum, stage) => sum + Number(stage.cost_usd), 0))}`
  const activeStage = stages.find(stage => stage.id === sourceTab)

  return {
    stages, activeStage, totalCost, erpRows,
    filteredDocuments: rows.filter(document => document.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())),
    search, onSearch: setSearch, onBack,
    selected,
    loading, pdfUrl, pdfLoading, deleting, sourceTab, watchDocuments,
    onRetry, retrying,
    selectedRow: rows.find(document => document.id === selectedId),
    view, onUsage: () => { onBack(); setView('usage') },
    onUpload, onDelete, onSelect: (id: string) => { setView('documents'); return selectDocument(id) }, onSourceTab: setSourceTab,
    labels: {
      erp: t('erp.title'), totalTime: t('documents.totalTime'),
      totalCost: t('usage.totalCost'), pipeline: t('pipeline.title'), waiting: t('pipeline.waiting'), appName: t('app.name'), upload: t('documents.upload'),
      library: t('documents.library'), search: t('documents.search'), back: t('documents.back'),
      errorStatus: t('pipeline.status.error'), status: t('documents.status'), created: t('documents.created'), noResults: t('documents.noResults'),
      emptyList: t('documents.emptyList'), pdf: t('documents.pdf'),
      markdown: t('documents.markdown'),
      features: t('documents.features'), noFeatures: t('documents.noFeatures'),
      error: t('documents.error'), loading: t('documents.loading'),
      delete: t('documents.delete'),
      document: t('documents.document'),
      pdfError: t('documents.pdfError'),
      usage: t('usage.title'),
      retry: t('documents.retry'),
    },
    featureLabels: {
      invoiceNumber: t('features.invoiceNumber'), invoiceDate: t('features.invoiceDate'),
      purchaseOrder: t('features.purchaseOrder'), supplierName: t('features.supplierName'),
      supplierNif: t('features.supplierNif'), iban: t('features.iban'),
      lineItems: t('features.lineItems'), taxBase: t('features.taxBase'),
      vatRate: t('features.vatRate'), vatAmount: t('features.vatAmount'), total: t('features.total'),
    },
  }
}
