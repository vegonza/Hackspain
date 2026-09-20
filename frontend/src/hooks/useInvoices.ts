import { useCallback, useRef, useState, type ChangeEvent, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { invoicePath, useAppRoute } from '@/hooks/useAppRoute'
import { useInvoiceTable } from '@/hooks/useInvoiceTable'
import { useInvoiceImports, type InvoiceUpload } from '@/hooks/useInvoiceImports'
import { useInvoiceDetail } from '@/hooks/useInvoiceDetail'
import { useIdentifierTrace } from '@/hooks/useIdentifierTrace'
import { invoiceErrorKey } from '@/hooks/invoiceError'
import { invoiceMetrics } from '@/hooks/invoiceMetrics'
import { invoiceLineCategory } from '@/hooks/invoiceLineCategory'
import { deleteInvoice, redoInvoice, retryInvoice, fetchInvoices, uploadInvoice, type Invoice } from '@/api/invoices'
import { formatAmount, formatStatus } from '@/lib/format'
import { isSupportedInvoiceFile } from '@/lib/invoiceFiles'

const isProcessing = (document: Invoice) => document.status === 'queued' || document.status === 'processing'

export function useInvoices() {
  const { t } = useTranslation()
  const { view, invoiceId: selectedId, navigate, followLink } = useAppRoute()
  const [lineItemsState, setLineItemsState] = useState({ invoiceId: selectedId, expanded: false })
  if (lineItemsState.invoiceId !== selectedId) setLineItemsState({ invoiceId: selectedId, expanded: false })
  const lineItemsExpanded = lineItemsState.invoiceId === selectedId && lineItemsState.expanded
  const { selected, loading, pdfUrl, pdfLoading, mountDetail, refreshDetail, updateMetrics, sourceTab, onSourceTab, dataTab, onDataTab } = useInvoiceDetail(selectedId)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [invoicesLoading, setInvoicesLoading] = useState(true)
  const [uploads, setUploads] = useState<InvoiceUpload[]>([])
  const uploadsInFlight = useRef(new Set<string>())
  const imports = useInvoiceImports(invoices, uploads, view === 'invoices' && selectedId === null)
  const [deleting, setDeleting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [redoing, setRedoing] = useState(false)
  const redoInFlight = useRef(false)
  const invoicesRef = useRef<Invoice[]>([])
  const listRevision = useRef(0)
  const schedulePolling = useRef<(() => void) | null>(null)

  const updateInvoices = useCallback((next: Invoice[]) => {
    invoicesRef.current = next
    setInvoices(next)
    if (schedulePolling.current !== null) schedulePolling.current()
  }, [])

  const watchInvoices = useCallback((node: HTMLDivElement | null) => {
    if (node === null) return
    let active = true
    let timer: ReturnType<typeof setTimeout> | undefined
    let fetching = false
    function schedule(): void {
      clearTimeout(timer)
      timer = undefined
      if (active && !fetching && invoicesRef.current.some(isProcessing)) {
        timer = setTimeout(() => void poll(), 3000)
      }
    }
    async function poll(): Promise<void> {
      if (!active || fetching) return
      clearTimeout(timer)
      fetching = true
      try {
        if (!document.hidden) {
          const revision = listRevision.current
          const next = await fetchInvoices()
          if (!active) return
          if (revision === listRevision.current) {
            const previous = invoicesRef.current
            updateInvoices(next)
            setInvoicesLoading(false)
            updateMetrics(next)
            const previousById = new Map(previous.map(document => [document.id, document]))
            for (const document of next) {
              const old = previousById.get(document.id)
              if (old && old.status !== document.status && document.status === 'error') {
                toast.error(`${document.name}: ${t(invoiceErrorKey(document.last_error))}`)
              }
            }
            const wasProcessing = previous.some(document => document.id === selectedId && isProcessing(document))
            const oldSelected = previousById.get(selectedId === null ? '' : selectedId)
            const nextSelected = next.find(invoice => invoice.id === selectedId)
            const decisionChanged = oldSelected !== undefined && nextSelected !== undefined
              && JSON.stringify(oldSelected.payment_decision) !== JSON.stringify(nextSelected.payment_decision)
            if (wasProcessing || decisionChanged) await refreshDetail()
          }
        }
      } catch {
        // The API client displays polling errors.
      } finally {
        fetching = false
        schedule()
      }
    }
    function onVisibilityChange(): void {
      if (!document.hidden) void poll()
    }
    schedulePolling.current = schedule
    document.addEventListener('visibilitychange', onVisibilityChange)
    void poll()
    return () => {
      active = false
      clearTimeout(timer)
      schedulePolling.current = null
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [t, updateInvoices, updateMetrics, selectedId, refreshDetail])

  function onInvoiceLink(event: MouseEvent<HTMLAnchorElement>): void {
    event.stopPropagation()
    followLink(event)
  }

  async function onUpload(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const files = Array.from(event.target.files || [])
    event.target.value = ''
    if (files.length === 0) return
    const valid = files.filter(file => isSupportedInvoiceFile(file.name))
    if (valid.length !== files.length) toast.error(t('invoices.unsupportedFileType'))
    if (valid.length === 0) return
    const pending = valid.map(file => ({ id: `upload-${crypto.randomUUID()}`, name: file.name, file, status: 'queued' as const }))
    setUploads(current => [...pending, ...current])
    const tasks = pending.values()
    async function transfer(): Promise<void> {
      for (const item of tasks) {
        await transferUpload(item)
      }
    }
    await Promise.all(Array.from({ length: Math.min(3, pending.length) }, () => transfer()))
  }

  async function transferUpload(item: InvoiceUpload): Promise<void> {
    if (uploadsInFlight.current.has(item.id)) return
    uploadsInFlight.current.add(item.id)
    setUploads(current => current.map(upload => upload.id === item.id ? { ...upload, status: 'uploading' } : upload))
    try {
      const invoice = await uploadInvoice(item.file)
      ++listRevision.current
      imports.track(invoice.id)
      updateInvoices([invoice, ...invoicesRef.current.filter(existing => existing.id !== invoice.id)])
      setUploads(current => current.filter(upload => upload.id !== item.id))
    } catch {
      setUploads(current => current.map(upload => upload.id === item.id ? { ...upload, status: 'error' } : upload))
    } finally {
      uploadsInFlight.current.delete(item.id)
    }
  }

  async function onRetryImport(id: string): Promise<void> {
    const upload = uploads.find(item => item.id === id)
    if (upload !== undefined) await transferUpload(upload)
    else await onRedo(id)
  }

  async function onDelete(id: string): Promise<void> {
    if (deleting) return
    setDeleting(true)
    ++listRevision.current
    try {
      await deleteInvoice(id)
      ++listRevision.current
      updateInvoices(invoicesRef.current.filter(document => document.id !== id))
      if (selectedId === id) navigate('/invoices', true)
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
      const document = await retryInvoice(id)
      ++listRevision.current
      updateInvoices(invoicesRef.current.map(item => item.id === id ? document : item))
      if (selectedId === id) await refreshDetail()
    } catch {
      // The API client displays the error.
    } finally {
      setRetrying(false)
    }
  }

  async function onRedo(id: string): Promise<void> {
    if (redoInFlight.current) return
    redoInFlight.current = true
    setRedoing(true)
    ++listRevision.current
    try {
      const document = await redoInvoice(id)
      ++listRevision.current
      updateInvoices([document, ...invoicesRef.current.filter(item => item.id !== id)])
      if (selectedId === id) await refreshDetail()
    } catch {
      // The API client displays the error.
    } finally {
      redoInFlight.current = false
      setRedoing(false)
    }
  }

  const formatCost = (cost: string | null): string => cost === null ? '—' : `$${Number(cost).toFixed(4)}`
  const formatDuration = (duration: number | null): string => {
    if (duration === null) return '—'
    const centiseconds = Math.round(duration / 10)
    return centiseconds < 6000
      ? t('processing.durationSeconds', { value: (centiseconds / 100).toFixed(2) })
      : t('processing.durationMinutes', { minutes: Math.floor(centiseconds / 6000), seconds: ((centiseconds % 6000) / 100).toFixed(2) })
  }
  const table = useInvoiceTable(invoices, invoicesLoading)

  const erp = selected === null ? null : selected.erp
  const extraction = selected === null ? null : selected.extraction
  const featureMoney = (value: string, currency: string): string => value === '' ? t('extraction.unavailable')
    : formatAmount(Number(value), currency)
  const featureAmounts = extraction === null ? null : {
    taxBase: featureMoney(extraction.tax_base, extraction.currency),
    vatRate: extraction.vat_rate === '' ? t('extraction.unavailable') : `${extraction.vat_rate}%`,
    vatAmount: featureMoney(extraction.vat_amount, extraction.currency),
    total: featureMoney(extraction.total, extraction.currency),
    lineItems: (lineItemsExpanded ? extraction.line_items : extraction.line_items.slice(0, 3))
      .map(line => {
        const category = invoiceLineCategory(line.description)
        return {
          description: line.description, amount: featureMoney(line.amount, extraction.currency),
          category: category === undefined ? null : { icon: category.icon, label: t(`extraction.categories.${category.id}`) },
        }
      }),
    canExpandLineItems: extraction.line_items.length > 3,
    lineItemsExpanded,
    onToggleLineItems: () => setLineItemsState({ invoiceId: selectedId, expanded: !lineItemsExpanded }),
  }
  const difference = erp !== null && erp.amount !== null && extraction !== null && extraction.currency === 'EUR' && extraction.total !== ''
    ? Number(extraction.total) - Number(erp.amount) : null
  const erpRows = [
    { label: t('erp.status'), value: erp === null ? t('erp.notLinked') : formatStatus(erp.status) },
    { label: t('common.amount'), value: erp === null || erp.amount === null ? t('extraction.unavailable') : formatAmount(Number(erp.amount), 'EUR') },
    { label: t('erp.difference'), value: difference === null ? t('extraction.unavailable') : formatAmount(difference, 'EUR') },
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
  const selectedRow = invoices.find(document => document.id === selectedId)
  const metricsLoading = loading && selected === null && selectedRow === undefined
  const metrics = invoiceMetrics(selected, selectedRow)
  const totalDuration = formatDuration(metrics.total_duration_ms)
  const totalCost = formatCost(metrics.total_cost_usd)
  const emptyMessage = sourceTab === 'text' && selected !== null && selected.native_text !== null && selected.native_text.trim() === ''
    ? t('processing.noText') : null
  const extractionLoading = loading || (selected !== null && selected.extraction === null && isProcessing(selected))
  const identifierTrace = useIdentifierTrace(selected === null ? [] : selected.identifier_trace.identifier_corrections)

  return {
    redoing, onRedo,
    metricsLoading, emptyMessage, erpRows, totalDuration, totalCost, identifierTrace,
    table, imports, onRetryImport, invoicesLoading, onInvoiceLink, onNavigate: followLink,
    selected, selectedId, mountDetail, featureAmounts,
    loading, extractionLoading, pdfUrl, pdfLoading, deleting, sourceTab, onSourceTab, dataTab, onDataTab, watchInvoices,
    retrying,
    canRetry: (selected !== null && selected.status === 'error') || (selectedRow !== undefined && selectedRow.status === 'error'),
    onRetrySelected: () => { if (selectedId !== null) void onRetry(selectedId) },
    invoiceName: selected !== null ? selected.name : selectedRow === undefined ? null : selectedRow.name,
    supplierName: selected !== null && selected.extraction !== null ? selected.extraction.supplier_name : null,
    view,
    onUpload, onDelete, onSelect: (id: string) => navigate(invoicePath(id)),
    labels: {
      decision: t('invoices.decision'),
      processingSummary: t('invoices.processingSummary'),
      decisionLabel: selected === null || selected.payment_decision === null ? t('invoices.decisionPending') : t(`invoices.decisions.${selected.payment_decision.classification}`),
      count: t('invoices.count', { count: invoices.length }),
      erp: t('erp.title'), erpData: t('erp.dataTitle'), totalTime: t('invoices.totalTime'),
      totalCost: t('usage.totalCost'), waiting: t('processing.waiting'), appName: t('app.name'), upload: t('invoices.upload'),
      library: t('invoices.library'), search: t('invoices.search'), back: t('invoices.back'),
      errorStatus: t('invoices.errorStatus'), status: t('invoices.status'), created: t('invoices.created'), noResults: t('invoices.noResults'),
      emptyList: t('invoices.emptyList'), pdf: t('invoices.pdf'),
      text: t('invoices.text'), extraction: t('invoices.extraction'), noExtraction: t('invoices.noExtraction'),
      error: t(invoiceErrorKey(selected !== null ? selected.last_error : selectedRow === undefined ? null : selectedRow.last_error)), loading: t('invoices.loading'),
      delete: t('invoices.delete'),
      invoice: t('invoices.invoice'),
      pdfError: t('invoices.pdfError'), invoiceUnavailable: t('invoices.unavailable'),
      notFound: t('invoices.pageNotFound'),
      usage: t('usage.title'),
      retry: t('invoices.retry'),
      redo: t('invoices.redo'),
      actions: t('invoices.actions'),
    },
    extractionLabels: {
      inferred: t('extraction.identifierTrace'),
      notes: t('extraction.notes'), uncertainties: t('extraction.uncertainties'),
      invoiceNumber: t('extraction.invoiceNumber'), invoiceDate: t('extraction.invoiceDate'),
      purchaseOrder: t('extraction.purchaseOrder'),
      supplierNif: t('extraction.supplierNif'), iban: t('extraction.iban'),
      lineItems: t('extraction.lineItems'), taxBase: t('extraction.taxBase'),
      showMore: t('extraction.showMore'), showLess: t('extraction.showLess'),
      vatRate: t('extraction.vatRate'), vatAmount: t('extraction.vatAmount'), total: t('extraction.total'),
    },
  }
}
