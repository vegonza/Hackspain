import { LoaderCircle, Upload } from 'lucide-react'
import logo from '@/assets/logo.svg'
import type { useDocuments } from '@/hooks/useDocuments'
import { ReviewSkeleton } from '@/components/documents/ReviewSkeleton'
import { Markdown } from '@/components/documents/Markdown'
import { DeleteButton } from '@/components/ui/delete-button'
import { PdfViewer } from '@/components/documents/PdfViewer'
import { InvoiceFeatures } from '@/components/documents/InvoiceFeatures'
import { InvoiceFeaturesSkeleton } from '@/components/documents/InvoiceFeaturesSkeleton'
import { DocumentSkeleton } from '@/components/documents/DocumentSkeleton'

type Props = ReturnType<typeof useDocuments>

export function DocumentsView({ documents, selected, selectedId, selectedRow, loading, pdfUrl, pdfLoading, uploadSelected, deleting, sourceTab, watchDocuments, onSourceTab, onUpload, onDelete, onSelect, labels, featureLabels }: Props) {
  return (
    <div className="app-shell" ref={watchDocuments}>
      <header className="app-header">
        <img className="brand-logo" src={logo} alt={labels.appName} />
        <span className="header-divider" />
        <h1>{labels.library}</h1>
        <span className="document-count">{documents.length}</span>
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
                <div key={document.id} className="document-row" data-selected={selectedId === document.id}>
                  <button className="document-item" aria-current={selectedId === document.id ? 'true' : undefined}
                    onClick={() => void onSelect(document.id)}>
                    <span className="document-name" title={document.name}>{document.name}</span>
                    {document.pending && <LoaderCircle size={15} className="upload-spinner" aria-label={document.statusLabel} />}
                    {document.status === 'error' && <span className="error-dot" title={labels.error} />}
                  </button>
                  {!document.pending && <DeleteButton label={labels.delete} confirmation={document.deleteConfirmation}
                    disabled={deleting} onDelete={() => void onDelete(document.id)} />}
                </div>
              ))}
            </nav>
          </aside>
          {uploadSelected ? (
            <ReviewSkeleton label={labels.loading} />
          ) : selectedRow ? (
            <div className="review-desk">
              <section className="viewer-panel" aria-label={sourceTab === 'pdf' ? labels.pdf : labels.markdown}>
                <header className="source-header">
                  <h2 title={selectedRow.name}>{selectedRow.name}</h2>
                  <div className="source-tabs" role="group" aria-label={labels.document}>
                    <button aria-pressed={sourceTab === 'pdf'} onClick={() => onSourceTab('pdf')}>{labels.pdf}</button>
                    <button aria-pressed={sourceTab === 'markdown'} onClick={() => onSourceTab('markdown')}>{labels.markdown}</button>
                  </div>
                </header>
                <div className="source-body" hidden={sourceTab !== 'pdf'}>
                  {pdfUrl ? <PdfViewer key={selectedRow.id} url={pdfUrl} /> : pdfLoading ? (
                    <div className="pdf-viewer" role="status" aria-label={labels.loading}>
                      <div className="pdf-scroll"><div className="pdf-page aspect-[210/297]"><DocumentSkeleton /></div></div>
                    </div>
                  ) : <p className="markdown-error">{labels.pdfError}</p>}
                </div>
                {sourceTab === 'markdown' && <div className="markdown-scroll">
                  {loading ? <DocumentSkeleton /> : selected && selected.status === 'ready' ? <Markdown content={selected.markdown} /> : <p className="markdown-error">{labels.noMarkdown}</p>}
                </div>}
              </section>
              <section className="features-panel" aria-label={labels.features} aria-busy={loading}>
                <header className="review-header"><h2>{labels.features}</h2></header>
                {loading ? <InvoiceFeaturesSkeleton /> : selected && selected.features ?
                  <InvoiceFeatures features={selected.features} labels={featureLabels} />
                : <p className="markdown-error">{labels.noFeatures}</p>}
              </section>
            </div>
          ) : <div className="empty-review"><p>{labels.emptyDescription}</p></div>}
        </main>
    </div>
  )
}
