import { MarkdownDiff } from '@/components/documents/MarkdownDiff'
import { DocumentErp } from '@/components/documents/DocumentErp'
import { DocumentPipeline } from '@/components/documents/DocumentPipeline'
import { Skeleton } from '@/components/ui/skeleton'
import { DollarSign, LoaderCircle, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import { UsageView } from '@/components/usage/UsageView'
import type { useUsage } from '@/hooks/useUsage'
import logo from '@/assets/logo.svg'
import type { useDocuments } from '@/hooks/useDocuments'
import { ReviewSkeleton } from '@/components/documents/ReviewSkeleton'
import { Markdown } from '@/components/documents/Markdown'
import { DeleteButton } from '@/components/ui/delete-button'
import { PdfViewer } from '@/components/documents/PdfViewer'
import { InvoiceFeatures } from '@/components/documents/InvoiceFeatures'
import { InvoiceFeaturesSkeleton } from '@/components/documents/InvoiceFeaturesSkeleton'
import { DocumentSkeleton } from '@/components/documents/DocumentSkeleton'

type Props = ReturnType<typeof useDocuments> & { usage: ReturnType<typeof useUsage> }

export function DocumentsView({ erpRows, stages, activeStage, totalCost, documents, selected, selectedId, selectedRow, loading, pdfUrl, pdfLoading, uploadSelected, deleting, sourceTab, watchDocuments, onSourceTab, onUpload, onDelete, onSelect, labels, featureLabels, view, onUsage, usage, onRetry, retrying }: Props) {
  return (
    <div className="app-shell" ref={watchDocuments}>
      <header className="app-header">
        <img className="brand-logo" src={logo} alt={labels.appName} />
        {view === 'usage' && <h1>{labels.usage}</h1>}
        <label className="upload-button">
          <Upload size={15} />{labels.upload}
          <input type="file" accept="application/pdf,.pdf" multiple onChange={onUpload} aria-label={labels.upload} />
        </label>
      </header>
        <main className="review-layout">
          <aside className="sidebar">
            <nav className="document-list" aria-label={labels.library}>
              {documents.length === 0 && <p className="empty-list">{labels.emptyList}</p>}
              {documents.map(document => (
                <div key={document.id} className="document-row" data-selected={view === 'documents' && selectedId === document.id}>
                  <Button variant="sidebar" size="sidebar" className="document-item" aria-current={view === 'documents' && selectedId === document.id ? 'true' : undefined}
                    onClick={() => void onSelect(document.id)}>
                    <Tooltip text={document.name} onlyWhenTruncated asChild><span className="document-name">{document.name}</span></Tooltip>
                    {document.pending && <Tooltip text={document.statusLabel} asChild><span className="ml-auto flex"><LoaderCircle size={15} className="upload-spinner" aria-label={document.statusLabel} /></span></Tooltip>}
                    {document.status === 'error' && <Tooltip text={document.errorMessage || labels.error} asChild><span className="error-dot" aria-label={labels.error} /></Tooltip>}
                  </Button>
                  {!document.pending && <DeleteButton label={labels.delete} confirmation={document.deleteConfirmation}
                    disabled={deleting} onDelete={() => void onDelete(document.id)} />}
                </div>
              ))}
            </nav>
            <Button variant="sidebar" size="sidebar" className={`mt-3 [&>svg]:text-muted-foreground ${view === 'usage' ? 'bg-selected hover:bg-selected' : ''}`} aria-current={view === 'usage' ? 'page' : undefined} onClick={onUsage}><DollarSign /><span>{labels.usage}</span></Button>
          </aside>
          {view === 'usage' ? <UsageView {...usage} /> : uploadSelected ? (
            <ReviewSkeleton label={labels.loading} />
          ) : selectedRow ? (
            <div className="review-desk">
              <section className="viewer-panel" aria-label={sourceTab === 'pdf' ? labels.pdf : labels.markdown}>
                <header className="source-header">
                  <Tooltip text={selectedRow.name} onlyWhenTruncated asChild><h2>{selectedRow.name}</h2></Tooltip>
                  {selectedRow.status === 'error' && <Button variant="outline" size="sm" disabled={retrying} onClick={() => void onRetry(selectedRow.id)}>{labels.retry}</Button>}
                  <div className="source-tabs" role="group" aria-label={labels.document}>
                    <button aria-pressed={sourceTab === 'pdf'} onClick={() => onSourceTab('pdf')}>{labels.pdf}</button>
                    {stages.map(stage => <button key={stage.id} aria-pressed={sourceTab === stage.id} onClick={() => onSourceTab(stage.id)}>{stage.label}</button>)}
                  </div>
                </header>
                <div className="source-body" hidden={sourceTab !== 'pdf'}>
                  {pdfUrl ? <PdfViewer key={selectedRow.id} url={pdfUrl} /> : pdfLoading ? (
                    <div className="pdf-viewer" role="status" aria-label={labels.loading}>
                      <div className="pdf-scroll"><div className="pdf-page aspect-[210/297]"><DocumentSkeleton /></div></div>
                    </div>
                  ) : <p className="markdown-error">{labels.pdfError}</p>}
                </div>
                {sourceTab !== 'pdf' && <div className="markdown-scroll">
                  {loading || (activeStage && (activeStage.status === 'processing' || activeStage.status === 'retrying')) ? <DocumentSkeleton />
                    : activeStage && activeStage.diff !== null ? <MarkdownDiff lines={activeStage.diff} labels={labels.diff} />
                    : activeStage && activeStage.content !== null ? activeStage.format === 'markdown'
                      ? <Markdown content={activeStage.content} /> : <pre className="extracted-text">{activeStage.content}</pre>
                    : activeStage && <div className="stage-empty"><h3>{activeStage.label}</h3><p>{activeStage.description}</p>{activeStage.status !== 'unavailable' && <span>{activeStage.statusLabel}</span>}<p>{activeStage.status === 'error' ? labels.error : activeStage.status !== 'unavailable' ? labels.waiting : ''}</p></div>}
                </div>}
              </section>
              <section className="features-panel" aria-label={labels.features} aria-busy={loading}>
                {loading ? <div className="pipeline-skeleton"><Skeleton className="h-3 w-20" />{[0, 1, 2].map(index => <Skeleton key={index} className="h-12 w-full" />)}</div>
                  : <DocumentPipeline totalCost={totalCost} totalLabel={labels.totalCost} title={labels.pipeline} stages={stages} selected={sourceTab} onSelect={onSourceTab} />}
                <header className="review-header"><h2>{labels.features}</h2></header>
                {selectedRow.status === 'error' && selectedRow.errorMessage && <p role="alert" className="markdown-error">{selectedRow.errorMessage}</p>}
                {loading ? <InvoiceFeaturesSkeleton /> : selected && selected.features ?
                  <InvoiceFeatures features={selected.features} labels={featureLabels} />
                : <p className="markdown-error">{labels.noFeatures}</p>}
                <DocumentErp title={labels.erp} loading={loading} rows={erpRows} />
              </section>
            </div>
          ) : <div className="empty-review"><p>{labels.emptyDescription}</p></div>}
        </main>
    </div>
  )
}
