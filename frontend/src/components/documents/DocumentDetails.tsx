import { ArrowLeft, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { DocumentErp } from '@/components/documents/DocumentErp'
import { DocumentPipeline } from '@/components/documents/DocumentPipeline'
import { DocumentSkeleton } from '@/components/documents/DocumentSkeleton'
import { InvoiceExtraction } from '@/components/documents/InvoiceExtraction'
import { InvoiceExtractionSkeleton } from '@/components/documents/InvoiceExtractionSkeleton'
import { Markdown } from '@/components/documents/Markdown'
import { PdfViewer } from '@/components/documents/PdfViewer'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import type { useDocuments } from '@/hooks/useDocuments'

type Props = Pick<ReturnType<typeof useDocuments>,
  'mountDetail' | 'documentName' | 'selectedId' | 'selected' | 'loading' | 'extractionLoading' |
  'pdfUrl' | 'pdfLoading' | 'sourceTab' | 'activeStage' | 'emptyMessage' | 'labels' | 'extractionLabels' |
  'canRetry' | 'onRetrySelected' | 'retrying' | 'stageNavigation' | 'metricsLoading' | 'totalDuration' | 'totalCost' |
  'onNavigate' | 'onSourceTab' | 'erpRows' | 'featureAmounts'>

export function DocumentDetails({ mountDetail, documentName, selectedId, selected, loading, extractionLoading,
  pdfUrl, pdfLoading, sourceTab, activeStage, emptyMessage, labels, extractionLabels, canRetry, onRetrySelected,
  retrying, stageNavigation, metricsLoading, onNavigate, onSourceTab, erpRows, totalDuration, totalCost, featureAmounts }: Props) {
  return (
    <div className="review-desk" ref={mountDetail}>
      <aside className="document-sidebar" aria-label={labels.document}>
        <header className="document-sidebar-header">
          <Button variant="ghost" size="icon-sm" asChild>
            <a href="/docs" onClick={onNavigate} aria-label={labels.back}><ArrowLeft size={16} /></a>
          </Button>
          {documentName !== null
            ? <Tooltip text={documentName} onlyWhenTruncated asChild><h1>{documentName}</h1></Tooltip>
            : loading ? <Skeleton className="h-4 flex-1" /> : <h1>{labels.documentUnavailable}</h1>}
        </header>
        <DocumentPipeline label={labels.document} stageNavigation={stageNavigation} metricsLoading={metricsLoading}
          sourceTab={sourceTab} onSourceTab={onSourceTab} pdfLabel={labels.pdf} erpLabel={labels.erp} />
        <dl className="document-totals" aria-busy={metricsLoading}>
          <div><dt>{labels.totalTime}</dt><dd>{metricsLoading ? <Skeleton className="h-4 w-16" /> : totalDuration}</dd></div>
          <div><dt>{labels.totalCost}</dt><dd>{metricsLoading ? <Skeleton className="h-4 w-16" /> : totalCost}</dd></div>
        </dl>
      </aside>
      <section className="viewer-panel" aria-label={sourceTab === 'pdf' ? labels.pdf : sourceTab === 'erp' ? labels.erp : activeStage === undefined ? labels.document : activeStage.label}>
        {canRetry && <div className="document-retry"><span role="alert">{labels.error}</span><Button variant="outline" size="sm" disabled={retrying} onClick={onRetrySelected}>{labels.retry}</Button></div>}
        {!loading && selected === null ? <p role="alert" className="markdown-error">{labels.documentUnavailable}</p> : <>
          <div className="source-body" hidden={sourceTab !== 'pdf'}>
            {pdfUrl !== null ? <PdfViewer key={selectedId} url={pdfUrl} /> : pdfLoading ? (
              <div className="pdf-viewer">
                <div className="pdf-scroll"><LoadingSpinner label={labels.loading} /></div>
              </div>
            ) : <p className="markdown-error">{labels.pdfError}</p>}
          </div>
          {sourceTab === 'erp' && <div className="markdown-scroll"><DocumentErp title={labels.erpData} loading={loading} rows={erpRows} /></div>}
          {sourceTab !== 'pdf' && sourceTab !== 'erp' && <div className={`markdown-scroll${emptyMessage !== null ? ' document-empty-view' : ''}`}>
            {sourceTab === 'extraction' && extractionLoading ? <InvoiceExtractionSkeleton title={labels.extraction} />
              : loading || (activeStage && (activeStage.status === 'processing' || activeStage.status === 'retrying')) ? <DocumentSkeleton />
              : sourceTab === 'extraction' && selected !== null && selected.extraction !== null && featureAmounts !== null ? <InvoiceExtraction title={labels.extraction} extraction={selected.extraction} amounts={featureAmounts} labels={extractionLabels} />
              : emptyMessage !== null ? <div className="document-empty" role="status"><FileText size={32} strokeWidth={1.5} aria-hidden="true" /><p>{emptyMessage}</p></div>
              : activeStage && activeStage.content !== null ? activeStage.format === 'markdown'
                ? <Markdown content={activeStage.content} /> : <pre className="extracted-text">{activeStage.content}</pre>
              : activeStage && <div className="stage-empty"><h3>{activeStage.label}</h3><p>{activeStage.description}</p>{activeStage.status !== 'unavailable' && <span>{activeStage.statusLabel}</span>}<p>{activeStage.status === 'error' ? labels.error : activeStage.status !== 'unavailable' ? labels.waiting : ''}</p></div>}
          </div>}
        </>}
      </section>
    </div>
  )
}
