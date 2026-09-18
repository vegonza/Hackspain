import { useRef, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { deleteDocument, fetchDocument, fetchDocuments, uploadDocument, type Document, type DocumentDetail } from '@/api/documents'

export function useDocuments(initialDocuments: Document[]) {
  const { t } = useTranslation()
  const [documents, setDocuments] = useState(initialDocuments)
  const [selected, setSelected] = useState<DocumentDetail | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [sourceTab, setSourceTab] = useState<'pdf' | 'markdown'>('pdf')
  const selectionRequest = useRef(0)

  async function selectDocument(id: string): Promise<void> {
    const request = ++selectionRequest.current
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
    ++selectionRequest.current
    setLoading(false)
    setUploading(true)
    try {
      const document = await uploadDocument(file)
      setSelected(document)
      setSelectedId(document.id)
      setSourceTab('pdf')
    } catch {
      // The API client displays errors; the saved PDF remains in the list.
    } finally {
      try {
        setDocuments(await fetchDocuments())
      } catch {
        // Keep the current list when refreshing it fails.
      }
      setUploading(false)
    }
  }

  async function onDelete(id: string): Promise<void> {
    if (deleting) return
    setDeleting(true)
    try {
      await deleteDocument(id)
      setDocuments(current => current.filter(document => document.id !== id))
      if (selectedId === id) {
        ++selectionRequest.current
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
    selected, selectedId, loading, uploading, deleting, sourceTab,
    onUpload, onDelete, onSelect: selectDocument, onSourceTab: setSourceTab,
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
