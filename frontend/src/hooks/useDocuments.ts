import { useRef, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { deleteDocument, fetchDocument, fetchDocuments, uploadDocument, type Document, type DocumentDetail } from '@/api/documents'

const UPLOADING_ID = 'uploading'

export function useDocuments(initialDocuments: Document[]) {
  const { t } = useTranslation()
  const [documents, setDocuments] = useState(initialDocuments)
  const [selected, setSelected] = useState<DocumentDetail | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [uploadName, setUploadName] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [sourceTab, setSourceTab] = useState<'pdf' | 'markdown'>('pdf')
  const selectionRequest = useRef(0)
  const activeId = useRef<string | null>(null)

  function selectUpload(): void {
    ++selectionRequest.current
    activeId.current = UPLOADING_ID
    setSelectedId(UPLOADING_ID)
    setSelected(null)
    setLoading(false)
  }

  async function selectDocument(id: string): Promise<void> {
    const request = ++selectionRequest.current
    activeId.current = id
    setSelectedId(id)
    setSourceTab('pdf')
    setLoading(true)
    try {
      const document = await fetchDocument(id)
      if (request === selectionRequest.current) setSelected(document)
    } catch {
      if (request === selectionRequest.current) {
        setSelected(null)
        setSelectedId(null)
        activeId.current = null
      }
    } finally {
      if (request === selectionRequest.current) setLoading(false)
    }
  }

  async function onUpload(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files && event.target.files[0]
    event.target.value = ''
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast.error(t('documents.invalidPdf'))
      return
    }
    setUploadName(file.name)
    selectUpload()
    try {
      const document = await uploadDocument(file)
      setDocuments(current => [document, ...current])
      if (activeId.current === UPLOADING_ID) {
        activeId.current = document.id
        setSelected(document)
        setSelectedId(document.id)
        setSourceTab('pdf')
      }
    } catch {
      // Failed OCR still saves the PDF on the server.
      try {
        setDocuments(await fetchDocuments())
      } catch {
        // Keep the current list when refreshing it fails.
      }
      if (activeId.current === UPLOADING_ID) {
        activeId.current = null
        setSelectedId(null)
        setSelected(null)
      }
    } finally {
      setUploadName(null)
    }
  }

  async function onDelete(id: string): Promise<void> {
    if (deleting) return
    setDeleting(true)
    try {
      await deleteDocument(id)
      setDocuments(current => current.filter(document => document.id !== id))
      if (activeId.current === id) {
        ++selectionRequest.current
        activeId.current = null
        setSelected(null)
        setSelectedId(null)
        setLoading(false)
      }
    } catch {
      // The API client displays the error; the document stays selected.
    } finally {
      setDeleting(false)
    }
  }

  return {
    documents: documents.map(document => ({
      ...document,
      deleteConfirmation: t('documents.deleteConfirmation', { name: document.name }),
    })),
    selected, selectedId, loading, uploading: uploadName !== null, uploadName, deleting, sourceTab,
    uploadSelected: selectedId === UPLOADING_ID,
    onUpload, onDelete, onSelect: selectDocument, onSelectUpload: selectUpload, onSourceTab: setSourceTab,
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
