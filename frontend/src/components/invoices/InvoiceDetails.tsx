import { InvoiceDecisionBadge } from '@/components/invoices/InvoiceDecisionBadge'
import { ArrowLeft, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { InvoiceErp } from '@/components/invoices/InvoiceErp'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { InvoiceSkeleton } from '@/components/invoices/InvoiceSkeleton'
import { InvoiceExtraction } from '@/components/invoices/InvoiceExtraction'
import { InvoiceExtractionSkeleton } from '@/components/invoices/InvoiceExtractionSkeleton'
import { PdfViewer } from '@/components/invoices/PdfViewer'
import type { useInvoices } from '@/hooks/useInvoices'

type Props = Pick<ReturnType<typeof useInvoices>,
  'mountDetail' | 'invoiceName' | 'supplierName' | 'selectedId' | 'selected' | 'loading' | 'extractionLoading' |
  'pdfUrl' | 'pdfLoading' | 'dataTab' | 'onDataTab' | 'sourceTab' | 'emptyMessage' | 'labels' | 'extractionLabels' |
  'canRetry' | 'onRetrySelected' | 'retrying' | 'metricsLoading' | 'totalDuration' | 'totalCost' |
  'onNavigate' | 'onSourceTab' | 'erpRows' | 'featureAmounts' | 'identifierTrace'>

export function InvoiceDetails({ mountDetail, invoiceName, supplierName, selectedId, selected, loading, extractionLoading,
  pdfUrl, pdfLoading, sourceTab, dataTab, onDataTab, emptyMessage, labels, extractionLabels, canRetry, onRetrySelected,
  retrying, metricsLoading, onNavigate, onSourceTab, erpRows, totalDuration, totalCost, featureAmounts, identifierTrace }: Props) {
  return (
    <div className="review-desk" ref={mountDetail}>
      <section className="viewer-panel invoice-source-pane" aria-label={labels.invoice}>
        <header className="invoice-pane-header">
          <Button variant="ghost" size="icon-sm" asChild>
            <a href="/invoices" onClick={onNavigate} aria-label={labels.back}><ArrowLeft size={16} /></a>
          </Button>
          {invoiceName !== null
            ? <Tooltip text={invoiceName} onlyWhenTruncated asChild><h1>{invoiceName}</h1></Tooltip>
            : loading ? <Skeleton className="h-4 flex-1" /> : <h1>{labels.invoiceUnavailable}</h1>}
          <SegmentedControl label={labels.invoice} value={sourceTab} onValueChange={onSourceTab} className="ml-auto shrink-0 [&>button]:min-h-6"
            options={[{ value: 'pdf', label: labels.pdf }, { value: 'text', label: labels.text }]} />
        </header>
        {!loading && selected === null ? <p role="alert" className="markdown-error">{labels.invoiceUnavailable}</p> : <>
          <div className="source-body" hidden={sourceTab !== 'pdf'} aria-label={labels.pdf}>
            {pdfUrl !== null ? <PdfViewer key={selectedId} url={pdfUrl} />
              : pdfLoading ? <div className="invoice-pdf-skeleton" aria-label={labels.loading} aria-busy="true"><Skeleton className="h-full w-full" /></div>
              : <p className="markdown-error">{labels.pdfError}</p>}
          </div>
          {sourceTab === 'text' && <div className={`markdown-scroll${emptyMessage !== null ? ' invoice-empty-view' : ''}`} aria-label={labels.text}>
            {loading || extractionLoading ? <InvoiceSkeleton />
              : emptyMessage !== null ? <div className="invoice-empty" role="status"><FileText size={32} strokeWidth={1.5} aria-hidden="true" /><p>{emptyMessage}</p></div>
              : selected !== null && selected.native_text !== null ? <pre className="extracted-text">{selected.native_text}</pre>
              : <p className="invoice-empty" role="status">{labels.noExtraction}</p>}
          </div>}
        </>}
      </section>
      <section className="viewer-panel invoice-result-pane" aria-label={labels.extraction}>
        <header className="invoice-pane-header">
          {extractionLoading ? <Skeleton className="h-5 w-48 max-w-full" />
            : supplierName !== null && supplierName !== '' ? <Tooltip text={supplierName} onlyWhenTruncated asChild><h2 className="invoice-company-name">{supplierName}</h2></Tooltip>
            : <h2>{labels.extraction}</h2>}
          <SegmentedControl label={labels.extraction} value={dataTab} onValueChange={onDataTab} className="ml-auto shrink-0 [&>button]:min-h-6"
            options={[{ value: 'extraction', label: labels.extraction }, { value: 'erp', label: labels.erp }]} />
        </header>
        {canRetry && <div className="invoice-retry"><span role="alert">{labels.error}</span><Button variant="outline" size="sm" disabled={retrying} onClick={onRetrySelected}>{labels.retry}</Button></div>}
        <div className="markdown-scroll invoice-result-scroll">
          <dl className="invoice-decision-summary" aria-busy={loading}>
            <dt>{labels.decision}</dt>
            <dd>{loading ? <Skeleton className="h-5 w-20" />
              : <InvoiceDecisionBadge classification={selected === null || selected.payment_decision === null ? null : selected.payment_decision.classification} label={labels.decisionLabel} />}</dd>
            <dd className="invoice-decision-reasons">
              {loading ? <Skeleton className="h-4 w-full" />
                : selected !== null && selected.payment_decision !== null && selected.payment_decision.reasons.length > 0 && <ul>{selected.payment_decision.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul>}
            </dd>
          </dl>
          {!loading && selected === null ? <p role="alert" className="markdown-error">{labels.invoiceUnavailable}</p>
            : dataTab === 'erp' ? <InvoiceErp loading={loading} rows={erpRows} />
            : extractionLoading ? <InvoiceExtractionSkeleton title={labels.extraction} />
            : selected !== null && selected.extraction !== null && featureAmounts !== null ? <InvoiceExtraction title={labels.extraction} extraction={selected.extraction} amounts={featureAmounts} labels={extractionLabels} identifierTrace={identifierTrace} />
            : <p className="invoice-empty" role="status">{labels.noExtraction}</p>}
          <section className="invoice-processing-summary" aria-label={labels.processingSummary}>
            <dl className="invoice-detail-metrics" aria-busy={metricsLoading}>
              <div><dt>{labels.totalCost}</dt><dd>{metricsLoading ? <Skeleton className="h-4 w-12" /> : totalCost}</dd></div>
              <div><dt>{labels.totalTime}</dt><dd>{metricsLoading ? <Skeleton className="h-4 w-12" /> : totalDuration}</dd></div>
            </dl>
          </section>
        </div>
      </section>
    </div>
  )
}
