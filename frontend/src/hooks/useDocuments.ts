import { useCallback, useRef, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { deleteDocument, fetchStageCosts, retryDocument, fetchDocument, fetchDocuments, fetchPdfUrl, uploadDocument, type Document, type DocumentDetail, type StageId } from '@/api/documents'

interface UploadingFile { id: string; name: string }

export function useDocuments(initialDocuments: Document[]) {
  const { t } = useTranslation()
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
    const request = ++selectionRequest.current
    activeId.current = id
    setSelectedId(id)
    setSourceTab('pdf')
    setSelected(null)
    setPdfUrl(null)
    setPdfLoading(false)
    if (id.startsWith('upload-')) {
      setLoading(false)
      return
    }
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
    if (node === null) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function poll(): Promise<void> {
      try {
        if (documentsRef.current.some(document => document.status === 'queued' || document.status === 'processing')) {
          const revision = listRevision.current
          const next = await fetchDocuments()
          if (!active) return
          if (revision === listRevision.current) {
            const previous = documentsRef.current
            updateDocuments(next)
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
        const id = activeId.current
        const request = selectionRequest.current
        if (id !== null && !id.startsWith('upload-')) {
          const costs = await fetchStageCosts(id)
          if (active && request === selectionRequest.current) {
            setSelected(current => current === null ? null : {
              ...current,
              stages: current.stages.map(stage => stage.id in costs ? { ...stage, cost_usd: costs[stage.id] } : stage),
            })
          }
        }
      } catch {
        // The API client displays polling errors.
      } finally {
        if (active) timer = setTimeout(() => void poll(), 2000)
      }
    }
    void poll()
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [t, updateDocuments])

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
    void selectDocument(pending[0].id)
    const tasks = pending.values()
    async function transfer(): Promise<void> {
      for (const item of tasks) {
        try {
          const document = await uploadDocument(item.file)
          ++listRevision.current
          updateDocuments([document, ...documentsRef.current.filter(existing => existing.id !== document.id)])
          if (activeId.current === item.id) {
            void selectDocument(document.id)
          }
        } catch {
          if (activeId.current === item.id) {
            activeId.current = null
            setSelectedId(null)
            setSelected(null)
          }
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

  const rows = [
    ...uploads.map(upload => ({ ...upload, status: 'uploading' as const })),
    ...documents,
  ].map(document => ({
    ...document,
    pending: document.status === 'uploading' || document.status === 'queued' || document.status === 'processing',
    statusLabel: document.status !== 'uploading' && document.next_retry_at !== null
      ? t('documents.retryQueued') : t(`documents.${document.status}`),
    deleteConfirmation: t('documents.deleteConfirmation', { name: document.name }),
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
    documents: rows,
    selected,
    selectedId, loading, pdfUrl, pdfLoading, deleting, sourceTab, watchDocuments,
    onRetry, retrying,
    selectedRow: rows.find(document => document.id === selectedId),
    uploadSelected: rows.some(document => document.id === selectedId && document.status === 'uploading'),
    view, onUsage: () => setView('usage'),
    onUpload, onDelete, onSelect: (id: string) => { setView('documents'); return selectDocument(id) }, onSourceTab: setSourceTab,
    labels: {
      erp: t('erp.title'),
      totalCost: t('usage.totalCost'), pipeline: t('pipeline.title'), waiting: t('pipeline.waiting'), appName: t('app.name'), upload: t('documents.upload'),
      library: t('documents.library'),
      emptyList: t('documents.emptyList'), emptyTitle: t('documents.emptyTitle'),
      emptyDescription: t('documents.emptyDescription'), pdf: t('documents.pdf'),
      markdown: t('documents.markdown'), noMarkdown: t('documents.noMarkdown'),
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
