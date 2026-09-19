import { useCallback, useRef, useState, type ChangeEvent, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateLong } from '@/lib/format'
import { toast } from 'sonner'
import { invoicePath, useAppRoute } from '@/hooks/useAppRoute'
import { useInvoiceDetail } from '@/hooks/useInvoiceDetail'
import { invoiceStageMetrics, totalStageDuration } from '@/hooks/invoiceMetrics'
import { deleteInvoice, redoInvoice, retryInvoice, fetchInvoices, uploadInvoice, type Invoice } from '@/api/invoices'

const isProcessing = (invoice: Invoice) => invoice.status === 'queued' || invoice.status === 'processing'

export type InvoiceSortColumn = 'name' | 'status' | 'cost' | 'duration' | 'created'

interface UploadingFile { id: string; name: string; created_at: string }

export function useInvoices() {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [sortColumn, setSortColumn] = useState<InvoiceSortColumn | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const onToggleSort = (column: InvoiceSortColumn) => {
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
  const { view, invoiceId: selectedId, navigate, followLink } = useAppRoute()
  const { selected, loading, pdfUrl, pdfLoading, mountDetail, refreshDetail, updateMetrics, sourceTab, onSourceTab } = useInvoiceDetail(selectedId)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [invoicesLoading, setInvoicesLoading] = useState(true)
  const [uploads, setUploads] = useState<UploadingFile[]>([])
  const [deleting, setDeleting] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [redoing, setRedoing] = useState(false)
  const redoInFlight = useRef(false)
  const invoicesRef = useRef<Invoice[]>([])
  const listRevision = useRef(0)

  const updateInvoices = useCallback((next: Invoice[]) => {
    invoicesRef.current = next
    setInvoices(next)
  }, [])

  const watchInvoices = useCallback((node: HTMLDivElement | null) => {
    if (node === null || view !== 'invoices') return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function poll(): Promise<void> {
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
            for (const invoice of next) {
              const old = previous.find(item => item.id === invoice.id)
              if (old && old.status !== invoice.status && invoice.status === 'error') {
                toast.error(t('invoices.processingFailed', { name: invoice.name }))
              }
            }
            const wasProcessing = previous.some(invoice => invoice.id === selectedId && isProcessing(invoice))
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
  }, [t, updateInvoices, updateMetrics, view, selectedId, refreshDetail])

  function onBack(): void {
    navigate('/invoices')
  }

  function onInvoiceLink(event: MouseEvent<HTMLAnchorElement>): void {
    event.stopPropagation()
    followLink(event)
  }

  async function onUpload(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const files = Array.from(event.target.files || [])
    event.target.value = ''
    if (files.length === 0) return
    const valid = files.filter(file => file.name.toLowerCase().endsWith('.pdf'))
    if (valid.length !== files.length) toast.error(t('invoices.invalidPdf'))
    if (valid.length === 0) return
    const pending = valid.map(file => ({ id: `upload-${crypto.randomUUID()}`, name: file.name, created_at: new Date().toISOString(), file }))
    setUploads(current => [...pending, ...current])
    onBack()
    setSearch('')
    const tasks = pending.values()
    async function transfer(): Promise<void> {
      for (const item of tasks) {
        try {
          const invoice = await uploadInvoice(item.file)
          ++listRevision.current
          updateInvoices([invoice, ...invoicesRef.current.filter(existing => existing.id !== invoice.id)])
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
      await deleteInvoice(id)
      ++listRevision.current
      updateInvoices(invoicesRef.current.filter(invoice => invoice.id !== id))
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
      const invoice = await retryInvoice(id)
      ++listRevision.current
      updateInvoices(invoicesRef.current.map(item => item.id === id ? invoice : item))
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
      const invoice = await redoInvoice(id)
      ++listRevision.current
      updateInvoices([invoice, ...invoicesRef.current.filter(item => item.id !== id)])
      if (selectedId === id) await refreshDetail()
    } catch {
      // The API client displays the error.
    } finally {
      redoInFlight.current = false
      setRedoing(false)
    }
  }

  const formatCost = (cost: string | null): string => cost === null ? '—' : `$${Number(cost).toFixed(4)}`
  const formatDuration = (duration: number | null): string => duration === null ? '—'
    : duration < 60000 ? t('pipeline.durationSeconds', { value: Math.floor(duration / 1000) })
    : t('pipeline.durationMinutes', { minutes: Math.floor(duration / 60000), seconds: Math.floor(duration % 60000 / 1000) })
  const rows = [
    ...uploads.map(upload => ({ ...upload, status: 'uploading' as const, finished_at: null, total_cost_usd: null, stage_metrics: [], current_stages: [] })),
    ...invoices,
  ].map(invoice => {
    const durationMs = totalStageDuration(invoice.stage_metrics)
    return {
      ...invoice,
      costLabel: formatCost(invoice.total_cost_usd),
      durationMs,
      href: invoicePath(invoice.id),
      durationLabel: formatDuration(durationMs),
      costBreakdown: invoice.stage_metrics.map(metric => ({ label: t(`pipeline.stages.${metric.stage}`), value: formatCost(metric.cost_usd) })),
      durationBreakdown: invoice.stage_metrics.map(metric => ({ label: t(`pipeline.stages.${metric.stage}`), value: formatDuration(metric.duration_ms) })),
      canOpen: invoice.status !== 'uploading',
      canDelete: (invoice.status === 'ready' || invoice.status === 'error'),
      canRedo: invoice.status === 'ready' || invoice.status === 'error',
      statusIcon: invoice.status === 'uploading' || invoice.status === 'processing' ? 'spinner'
        : invoice.status === 'queued' ? 'clock' : invoice.status === 'error' ? 'error' : null,
      statusLabel: invoice.status !== 'uploading' && invoice.next_retry_at !== null
        ? t('invoices.retryQueued') : t(`invoices.${invoice.status}`),
      deleteConfirmation: t('invoices.deleteConfirmation', { name: invoice.name }),
      redoConfirmation: t('invoices.redoConfirmation', { name: invoice.name }),
      dateLabel: invoice.status === 'uploading' ? '—' : formatDateLong(invoice.created_at, 'es-ES'),
      errorMessage: invoice.status === 'error' ? t('invoices.error') : '',
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
  const filteredInvoices = rows.filter(invoice => invoice.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))
  if (sortColumn !== null) filteredInvoices.sort((a, b) => {
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
  const selectedRow = rows.find(invoice => invoice.id === selectedId)
  const metricsLoading = loading && selected === null && selectedRow === undefined
  const stageMetrics = invoiceStageMetrics(selected, selectedRow)
  const stageNavigation = (['ocr', 'text', 'extraction'] as const).map(id => {
    const metric = stageMetrics.find(item => item.stage === id)
    return {
      id,
      label: t(`pipeline.stages.${id}`),
      costLabel: formatCost(id === 'text' ? '0' : metric === undefined ? null : metric.cost_usd),
      durationLabel: metric === undefined || metric.duration_ms === null ? null : formatDuration(metric.duration_ms),
    }
  })
  const totalDuration = formatDuration(totalStageDuration(stageMetrics))
  const totalCost = formatCost(String(stageMetrics.reduce((sum, metric) => sum + (metric.cost_usd === null ? 0 : Number(metric.cost_usd)), 0)))
  const activeStage = stages.find(stage => stage.id === sourceTab)
  const emptyMessage = activeStage !== undefined && activeStage.status === 'ready' && sourceTab !== 'extraction'
    ? activeStage.content === null || activeStage.content.trim() === '' ? t('pipeline.noText') : null
    : null
  const extractionLoading = loading || (selected !== null && selected.extraction === null && isProcessing(selected))

  return {
    redoing, onRedo,
    stageNavigation, metricsLoading, activeStage, emptyMessage, erpRows, totalDuration, totalCost,
    filteredInvoices, invoicesLoading, sortColumn, sortDirection, onToggleSort,
    search, onSearch: setSearch, onInvoiceLink, onNavigate: followLink,
    selected, selectedId, mountDetail, featureAmounts,
    loading, extractionLoading, pdfUrl, pdfLoading, deleting, sourceTab, onSourceTab, watchInvoices,
    retrying,
    canRetry: (selected !== null && selected.status === 'error') || (selectedRow !== undefined && selectedRow.status === 'error'),
    onRetrySelected: () => { if (selectedId !== null) void onRetry(selectedId) },
    invoiceName: selected !== null ? selected.name : selectedRow === undefined ? null : selectedRow.name,
    view,
    onUpload, onDelete, onSelect: (id: string) => navigate(invoicePath(id)),
    labels: {
      count: t('invoices.count', { count: rows.length }),
      erp: t('erp.title'), erpData: t('erp.dataTitle'), totalTime: t('invoices.totalTime'),
      totalCost: t('usage.totalCost'), waiting: t('pipeline.waiting'), appName: t('app.name'), upload: t('invoices.upload'),
      library: t('invoices.library'), search: t('invoices.search'), back: t('invoices.back'),
      errorStatus: t('pipeline.status.error'), status: t('invoices.status'), created: t('invoices.created'), noResults: t('invoices.noResults'),
      emptyList: t('invoices.emptyList'), pdf: t('invoices.pdf'),
      extraction: t('invoices.extraction'), noExtraction: t('invoices.noExtraction'),
      error: t('invoices.error'), loading: t('invoices.loading'),
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
      notes: t('extraction.notes'), uncertainties: t('extraction.uncertainties'),
      invoiceNumber: t('extraction.invoiceNumber'), invoiceDate: t('extraction.invoiceDate'),
      purchaseOrder: t('extraction.purchaseOrder'), supplierName: t('extraction.supplierName'),
      supplierNif: t('extraction.supplierNif'), iban: t('extraction.iban'),
      lineItems: t('extraction.lineItems'), taxBase: t('extraction.taxBase'),
      vatRate: t('extraction.vatRate'), vatAmount: t('extraction.vatAmount'), total: t('extraction.total'),
    },
  }
}
