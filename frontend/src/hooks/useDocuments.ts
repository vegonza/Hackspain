import { useCallback, useRef, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { deleteDocument, fetchDocument, fetchDocuments, fetchPdfUrl, uploadDocument, type Document, type DocumentDetail } from '@/api/documents'

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
  const [sourceTab, setSourceTab] = useState<'pdf' | 'markdown'>('pdf')
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
              if (document.id === activeId.current && old && old.status !== document.status
                && (document.status === 'ready' || document.status === 'error')) {
                void selectDocument(document.id)
              }
            }
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
  }, [selectDocument, t, updateDocuments])

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
            activeId.current = document.id
            setSelectedId(document.id)
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

  const rows = [
    ...uploads.map(upload => ({ ...upload, status: 'uploading' as const })),
    ...documents,
  ].map(document => ({
    ...document,
    pending: document.status === 'uploading' || document.status === 'queued' || document.status === 'processing',
    statusLabel: t(`documents.${document.status}`),
    deleteConfirmation: t('documents.deleteConfirmation', { name: document.name }),
  }))

  return {
    documents: rows,
    selected, selectedId, loading, pdfUrl, pdfLoading, deleting, sourceTab, watchDocuments,
    selectedRow: rows.find(document => document.id === selectedId),
    uploadSelected: rows.some(document => document.id === selectedId && document.pending),
    view, onUsage: () => setView('usage'),
    onUpload, onDelete, onSelect: (id: string) => { setView('documents'); return selectDocument(id) }, onSourceTab: setSourceTab,
    labels: {
      appName: t('app.name'), upload: t('documents.upload'),
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
