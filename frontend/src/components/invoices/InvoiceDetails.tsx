import { ArrowLeft, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { InvoiceErp } from '@/components/invoices/InvoiceErp'
import { InvoicePipeline } from '@/components/invoices/InvoicePipeline'
import { InvoiceSkeleton } from '@/components/invoices/InvoiceSkeleton'
import { InvoiceExtraction } from '@/components/invoices/InvoiceExtraction'
import { InvoiceExtractionSkeleton } from '@/components/invoices/InvoiceExtractionSkeleton'
import { Markdown } from '@/components/invoices/Markdown'
import { PdfViewer } from '@/components/invoices/PdfViewer'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import type { useInvoices } from '@/hooks/useInvoices'

type Props = Pick<ReturnType<typeof useInvoices>,
  'mountDetail' | 'invoiceName' | 'selectedId' | 'selected' | 'loading' | 'extractionLoading' |
  'pdfUrl' | 'pdfLoading' | 'sourceTab' | 'activeStage' | 'emptyMessage' | 'labels' | 'extractionLabels' |
  'canRetry' | 'onRetrySelected' | 'retrying' | 'stageNavigation' | 'metricsLoading' | 'totalDuration' | 'totalCost' |
  'onNavigate' | 'onSourceTab' | 'erpRows' | 'featureAmounts'>

export function InvoiceDetails({ mountDetail, invoiceName, selectedId, selected, loading, extractionLoading,
  pdfUrl, pdfLoading, sourceTab, activeStage, emptyMessage, labels, extractionLabels, canRetry, onRetrySelected,
  retrying, stageNavigation, metricsLoading, onNavigate, onSourceTab, erpRows, totalDuration, totalCost, featureAmounts }: Props) {
  return (
    <div className="review-desk" ref={mountDetail}>
      <aside className="invoice-sidebar" aria-label={labels.invoice}>
        <header className="invoice-sidebar-header">
          <Button variant="ghost" size="icon-sm" asChild>
            <a href="/invoices" onClick={onNavigate} aria-label={labels.back}><ArrowLeft size={16} /></a>
          </Button>
          {invoiceName !== null
            ? <Tooltip text={invoiceName} onlyWhenTruncated asChild><h1>{invoiceName}</h1></Tooltip>
            : loading ? <Skeleton className="h-4 flex-1" /> : <h1>{labels.invoiceUnavailable}</h1>}
        </header>
        <InvoicePipeline label={labels.invoice} stageNavigation={stageNavigation} metricsLoading={metricsLoading}
          sourceTab={sourceTab} onSourceTab={onSourceTab} pdfLabel={labels.pdf} erpLabel={labels.erp} />
        <dl className="invoice-totals" aria-busy={metricsLoading}>
          <div><dt>{labels.totalTime}</dt><dd>{metricsLoading ? <Skeleton className="h-4 w-16" /> : totalDuration}</dd></div>
          <div><dt>{labels.totalCost}</dt><dd>{metricsLoading ? <Skeleton className="h-4 w-16" /> : totalCost}</dd></div>
        </dl>
      </aside>
      <section className="viewer-panel" aria-label={sourceTab === 'pdf' ? labels.pdf : sourceTab === 'erp' ? labels.erp : activeStage === undefined ? labels.invoice : activeStage.label}>
        {canRetry && <div className="invoice-retry"><span role="alert">{labels.error}</span><Button variant="outline" size="sm" disabled={retrying} onClick={onRetrySelected}>{labels.retry}</Button></div>}
        {!loading && selected === null ? <p role="alert" className="markdown-error">{labels.invoiceUnavailable}</p> : <>
          <div className="source-body" hidden={sourceTab !== 'pdf'}>
            {pdfUrl !== null ? <PdfViewer key={selectedId} url={pdfUrl} /> : pdfLoading ? (
              <div className="pdf-viewer">
                <div className="pdf-scroll"><LoadingSpinner label={labels.loading} /></div>
              </div>
            ) : <p className="markdown-error">{labels.pdfError}</p>}
          </div>
          {sourceTab === 'erp' && <div className="markdown-scroll"><InvoiceErp title={labels.erpData} loading={loading} rows={erpRows} /></div>}
          {sourceTab !== 'pdf' && sourceTab !== 'erp' && <div className={`markdown-scroll${emptyMessage !== null ? ' invoice-empty-view' : ''}`}>
            {sourceTab === 'extraction' && extractionLoading ? <InvoiceExtractionSkeleton title={labels.extraction} />
              : loading || (activeStage && (activeStage.status === 'processing' || activeStage.status === 'retrying')) ? <InvoiceSkeleton />
              : sourceTab === 'extraction' && selected !== null && selected.extraction !== null && featureAmounts !== null ? <InvoiceExtraction title={labels.extraction} extraction={selected.extraction} amounts={featureAmounts} labels={extractionLabels} />
              : emptyMessage !== null ? <div className="invoice-empty" role="status"><FileText size={32} strokeWidth={1.5} aria-hidden="true" /><p>{emptyMessage}</p></div>
              : activeStage && activeStage.content !== null ? activeStage.format === 'markdown'
                ? <Markdown content={activeStage.content} /> : <pre className="extracted-text">{activeStage.content}</pre>
              : activeStage && <div className="stage-empty"><h3>{activeStage.label}</h3><p>{activeStage.description}</p>{activeStage.status !== 'unavailable' && <span>{activeStage.statusLabel}</span>}<p>{activeStage.status === 'error' ? labels.error : activeStage.status !== 'unavailable' ? labels.waiting : ''}</p></div>}
          </div>}
        </>}
      </section>
    </div>
  )
}
