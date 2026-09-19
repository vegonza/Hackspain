import { useCallback, useRef, useState, type ChangeEvent, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateLong } from '@/lib/format'
import { toast } from 'sonner'
import { documentPath, useAppRoute } from '@/hooks/useAppRoute'
import { useDocumentDetail } from '@/hooks/useDocumentDetail'
import { totalStageDuration } from '@/hooks/documentMetrics'
import { deleteDocument, retryDocument, fetchDocuments, uploadDocument, type Document } from '@/api/documents'

const isProcessing = (document: Document) => document.status === 'queued' || document.status === 'processing'

export type DocumentSortColumn = 'name' | 'status' | 'cost' | 'duration' | 'created'

interface UploadingFile { id: string; name: string; created_at: string }

export function useDocuments() {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [sortColumn, setSortColumn] = useState<DocumentSortColumn | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const onToggleSort = (column: DocumentSortColumn) => {
    if (sortColumn !== column) {
      setSortColumn(column)
      setSortDirection('asc')
    } else if (sortDirection === 'asc') {
      setSortDirection('desc')
    } else {
      setSortColumn(null)
      setSortDirection('asc')
    }
  }
  const { view, documentId: selectedId, navigate, followLink } = useAppRoute()
  const { selected, loading, pdfUrl, pdfLoading, mountDetail, refreshDetail, updateMetrics, sourceTab, onSourceTab } = useDocumentDetail(selectedId)
  const [documents, setDocuments] = useState<Document[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(true)
  const documentsLoaded = useRef(false)
  const [uploads, setUploads] = useState<UploadingFile[]>([])
  const [deleting, setDeleting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const documentsRef = useRef<Document[]>([])
  const listRevision = useRef(0)

  const updateDocuments = useCallback((next: Document[]) => {
    documentsRef.current = next
    setDocuments(next)
  }, [])

  const watchDocuments = useCallback((node: HTMLDivElement | null) => {
    if (node === null || view !== 'documents') return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function poll(): Promise<void> {
      try {
        if (!document.hidden && (!documentsLoaded.current || documentsRef.current.some(isProcessing))) {
          const revision = listRevision.current
          const next = await fetchDocuments()
          if (!active) return
          if (revision === listRevision.current) {
            const previous = documentsRef.current
            updateDocuments(next)
            documentsLoaded.current = true
            setDocumentsLoading(false)
            updateMetrics(next)
            for (const document of next) {
              const old = previous.find(item => item.id === document.id)
              if (old && old.status !== document.status && document.status === 'error') {
                toast.error(t('documents.processingFailed', { name: document.name }))
              }
            }
            const wasProcessing = previous.some(document => document.id === selectedId && isProcessing(document))
            if (wasProcessing) await refreshDetail()
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
  }, [t, updateDocuments, updateMetrics, view, selectedId, refreshDetail])

  function onBack(): void {
    navigate('/docs')
  }

  function onDocumentLink(event: MouseEvent<HTMLAnchorElement>): void {
    event.stopPropagation()
    followLink(event)
  }

  async function onUpload(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const files = Array.from(event.target.files || [])
    event.target.value = ''
    if (files.length === 0) return
    const valid = files.filter(file => file.name.toLowerCase().endsWith('.pdf'))
    if (valid.length !== files.length) toast.error(t('documents.invalidPdf'))
    if (valid.length === 0) return
    const pending = valid.map(file => ({ id: `upload-${crypto.randomUUID()}`, name: file.name, created_at: new Date().toISOString(), file }))
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
      if (selectedId === id) navigate('/docs', true)
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
      if (selectedId === id) await refreshDetail()
    } catch {
      // The API client displays the error.
    } finally {
      setRetrying(false)
    }
  }

  const formatCost = (cost: string | null): string => cost === null ? '—' : `$${Number(cost).toFixed(4)}`
  const formatDuration = (duration: number | null): string => duration === null ? '—'
    : duration < 60000 ? t('pipeline.durationSeconds', { value: Math.floor(duration / 1000) })
    : t('pipeline.durationMinutes', { minutes: Math.floor(duration / 60000), seconds: Math.floor(duration % 60000 / 1000) })
  const rows = [
    ...uploads.map(upload => ({ ...upload, status: 'uploading' as const, finished_at: null, total_cost_usd: null, stage_metrics: [], current_stages: [] })),
    ...documents,
  ].map(document => {
    const durationMs = totalStageDuration(document.stage_metrics)
    return {
      ...document,
      costLabel: formatCost(document.total_cost_usd),
      durationMs,
      href: documentPath(document.id),
      durationLabel: formatDuration(durationMs),
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
    }
  })

  const sortValue = (row: typeof rows[number]): string | number | null => {
    switch (sortColumn) {
      case 'name': return row.name
      case 'status': return row.statusLabel
      case 'cost': return row.total_cost_usd === null ? null : Number(row.total_cost_usd)
      case 'duration': return row.durationMs
      case 'created': return row.status === 'uploading' ? null : Date.parse(row.created_at)
      default: return null
    }
  }
  const filteredDocuments = rows.filter(document => document.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))
  if (sortColumn !== null) filteredDocuments.sort((a, b) => {
    const left = sortValue(a), right = sortValue(b)
    if (left === null) return right === null ? 0 : 1
    if (right === null) return -1
    const comparison = typeof left === 'number' && typeof right === 'number'
      ? left - right : String(left).localeCompare(String(right), 'es', { numeric: true, sensitivity: 'base' })
    return sortDirection === 'asc' ? comparison : -comparison
  })

  const stages = selected === null ? [] : selected.stages.map(stage => ({
    ...stage,
    label: t(`pipeline.stages.${stage.id}`),
    statusLabel: t(`pipeline.status.${stage.status}`),
    description: t(`pipeline.description.${stage.id}`),
  }))
  const erp = selected === null ? null : selected.erp
  const extraction = selected === null ? null : selected.extraction
  const featureMoney = (value: string): string => value === '' ? t('extraction.unavailable')
    : new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(Number(value))
  const featureAmounts = extraction === null ? null : {
    taxBase: featureMoney(extraction.tax_base),
    vatRate: extraction.vat_rate === '' ? t('extraction.unavailable') : `${extraction.vat_rate}%`,
    vatAmount: featureMoney(extraction.vat_amount),
    total: featureMoney(extraction.total),
    lineItems: extraction.line_items.map(line => `${line.description} · ${featureMoney(line.amount)}`).join(', '),
  }
  const erpMoney = (value: number) => `${new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)} €`
  const difference = erp !== null && erp.amount !== null && extraction !== null && extraction.total !== ''
    ? Number(extraction.total) - Number(erp.amount) : null
  const erpRows = [
    { label: t('erp.status'), value: erp === null ? t('erp.notLinked')
      : erp.status === 'PENDIENTE' || erp.status === 'PAGADA' ? t(`erp.states.${erp.status}`) : erp.status },
    { label: t('erp.expectedAmount'), value: erp === null || erp.amount === null ? t('extraction.unavailable') : erpMoney(Number(erp.amount)) },
    { label: t('erp.difference'), value: difference === null ? t('extraction.unavailable') : erpMoney(difference) },
    { label: t('erp.entry'), value: erp === null ? '—' : erp.entry_id },
    { label: t('erp.purchaseOrder'), value: erp === null ? '—' : erp.order_id },
    { label: t('erp.supplier'), value: erp === null ? '—' : erp.supplier_id },
    { label: t('erp.nif'), value: erp === null ? '—' : erp.tax_id },
    { label: t('erp.registeredAt'), value: erp === null || erp.date === null ? t('extraction.unavailable') : new Date(`${erp.date}T00:00:00`).toLocaleDateString('es-ES') },
    ...(erp === null ? [] : [
      { label: t('erp.rawAmount'), value: erp.raw_amount },
      { label: t('erp.rawDate'), value: erp.raw_date },
      ...(erp.warnings.length === 0 ? [] : [{ label: t('erp.warningsLabel'), value: erp.warnings.map(warning => t(`erp.warnings.${warning}`)).join('; ') }]),
    ]),
  ]
  const selectedRow = rows.find(document => document.id === selectedId)
  const metricsLoading = loading && selected === null && selectedRow === undefined
  const stageMetrics = selectedRow !== undefined ? selectedRow.stage_metrics
    : selected === null ? [] : selected.stages.map(stage => ({ stage: stage.id, cost_usd: stage.cost_usd, duration_ms: stage.duration_ms }))
  const stageNavigation = (['ocr', 'text', 'merge', 'extraction'] as const).map(id => {
    const metric = stageMetrics.find(item => item.stage === id)
    return {
      id,
      label: t(`pipeline.stages.${id}`),
      costLabel: id === 'text' ? formatCost('0') : metric === undefined || metric.cost_usd === null ? null : formatCost(metric.cost_usd),
      durationLabel: metric === undefined || metric.duration_ms === null ? null : formatDuration(metric.duration_ms),
    }
  })
  const totalDuration = formatDuration(totalStageDuration(stageMetrics))
  const totalCost = formatCost(String(stageMetrics.reduce((sum, metric) => sum + (metric.cost_usd === null ? 0 : Number(metric.cost_usd)), 0)))
  const activeStage = stages.find(stage => stage.id === sourceTab)
  const diffLabel = t('pipeline.diffChanges')
  const emptyMessage = activeStage !== undefined && activeStage.status === 'ready' && sourceTab !== 'extraction'
    ? activeStage.diff !== null
      ? activeStage.diff.some(line => line.kind !== 'equal') ? null : t('pipeline.diffUnchanged')
      : activeStage.content === null || activeStage.content.trim() === '' ? t('pipeline.noText') : null
    : null
  const extractionLoading = loading || (selected !== null && selected.extraction === null && isProcessing(selected))

  return {
    stageNavigation, metricsLoading, activeStage, diffLabel, emptyMessage, erpRows, totalDuration, totalCost,
    filteredDocuments, documentsLoading, sortColumn, sortDirection, onToggleSort,
    search, onSearch: setSearch, onDocumentLink, onNavigate: followLink,
    selected, selectedId, mountDetail, featureAmounts,
    loading, extractionLoading, pdfUrl, pdfLoading, deleting, sourceTab, onSourceTab, watchDocuments,
    retrying,
    canRetry: (selected !== null && selected.status === 'error') || (selectedRow !== undefined && selectedRow.status === 'error'),
    onRetrySelected: () => { if (selectedId !== null) void onRetry(selectedId) },
    documentName: selected !== null ? selected.name : selectedRow === undefined ? null : selectedRow.name,
    view,
    onUpload, onDelete, onSelect: (id: string) => navigate(documentPath(id)),
    labels: {
      erp: t('erp.title'), erpData: t('erp.dataTitle'), totalTime: t('documents.totalTime'),
      totalCost: t('usage.totalCost'), waiting: t('pipeline.waiting'), appName: t('app.name'), upload: t('documents.upload'),
      library: t('documents.library'), search: t('documents.search'), back: t('documents.back'),
      errorStatus: t('pipeline.status.error'), status: t('documents.status'), created: t('documents.created'), noResults: t('documents.noResults'),
      emptyList: t('documents.emptyList'), pdf: t('documents.pdf'),
      extraction: t('documents.extraction'), noExtraction: t('documents.noExtraction'),
      error: t('documents.error'), loading: t('documents.loading'),
      delete: t('documents.delete'),
      document: t('documents.document'),
      pdfError: t('documents.pdfError'), documentUnavailable: t('documents.unavailable'),
      notFound: t('documents.pageNotFound'),
      usage: t('usage.title'),
      retry: t('documents.retry'),
    },
    extractionLabels: {
      notes: t('extraction.notes'), uncertainties: t('extraction.uncertainties'),
      invoiceNumber: t('extraction.invoiceNumber'), invoiceDate: t('extraction.invoiceDate'),
      purchaseOrder: t('extraction.purchaseOrder'), supplierName: t('extraction.supplierName'),
      supplierNif: t('extraction.supplierNif'), iban: t('extraction.iban'),
      lineItems: t('extraction.lineItems'), taxBase: t('extraction.taxBase'),
      vatRate: t('extraction.vatRate'), vatAmount: t('extraction.vatAmount'), total: t('extraction.total'),
    },
  }
}
