import { FileText, Upload } from 'lucide-react'
import logo from '@/assets/logo.jpeg'
import type { useDocuments } from '@/hooks/useDocuments'
import { DocumentSkeleton } from '@/components/documents/DocumentSkeleton'
import { Markdown } from '@/components/documents/Markdown'
import { DeleteButton } from '@/components/ui/delete-button'
import { PdfViewer } from '@/components/documents/PdfViewer'
import { Skeleton } from '@/components/ui/skeleton'
import { InvoiceFeatures } from '@/components/documents/InvoiceFeatures'

type Props = ReturnType<typeof useDocuments>

export function DocumentsView({ documents, selected, selectedId, loading, uploading, deleting, onUpload, onDelete, onSelect, labels, featureLabels }: Props) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><img src={logo} alt={labels.appName} /></div>
        <div className="library-label">{labels.library}<span>{documents.length}</span></div>
        <nav className="document-list" aria-label={labels.library}>
          {uploading && <div className="flex items-center gap-3 px-2.5 py-3" aria-busy="true">
            <Skeleton className="size-4 shrink-0" />
            <Skeleton className="h-4 w-36" />
          </div>}
          {documents.length === 0 && !uploading && <p className="empty-list">{labels.emptyList}</p>}
          {documents.map(document => (
            <div key={document.id} className="document-row" data-selected={selectedId === document.id}>
              <button className="document-item" aria-current={selectedId === document.id ? 'true' : undefined}
                disabled={uploading || deleting} onClick={() => void onSelect(document.id)}>
                <FileText size={17} />
                <span className="document-name" title={document.name}>{document.name}</span>
                {document.status === 'error' && <span className="error-dot" title={labels.error} aria-label={labels.error} />}
              </button>
              <DeleteButton label={labels.delete} confirmation={document.deleteConfirmation}
                disabled={uploading || deleting} onDelete={() => void onDelete(document.id)} />
            </div>
          ))}
        </nav>
      </aside>
      <main className="workspace">
        <header className="workspace-header">
          {uploading ? <Skeleton className="h-4 w-48" /> : selected && <h1 title={selected.name}>{selected.name}</h1>}
        <label className={`upload-button ${uploading ? 'disabled' : ''}`}>
          <Upload size={16} />{labels.upload}
          <input type="file" accept="application/pdf,.pdf" onChange={onUpload} disabled={uploading || deleting} aria-label={labels.upload} />
        </label>
        </header>
        {loading || uploading ? (
          <div className="loading-workspace" role="status" aria-label={labels.loading}>
            <div className="viewer-grid"><DocumentSkeleton /><DocumentSkeleton /></div>
          </div>
        ) : selected ? (
          <div className="document-content">
            <div className="viewer-grid">
              <section className="viewer-panel" aria-label={labels.pdf}>
                <div className="viewer-label-row"><span className="viewer-label">{labels.pdf}</span></div>
                <PdfViewer key={selected.id} documentId={selected.id} />
              </section>
              <section className="viewer-panel" aria-label={labels.markdown}>
                <div className="viewer-label-row"><span className="viewer-label">{labels.markdown}</span></div>
                <div className="markdown-scroll">
                  {selected.status === 'ready'
                    ? <Markdown content={selected.markdown} />
                    : <p className="markdown-error">{labels.noMarkdown}</p>}
                </div>
              </section>
            </div>
            <section className="features-panel" aria-label={labels.features}>
              <div className="viewer-label-row"><span className="viewer-label">{labels.features}</span></div>
              {selected.features
                ? <InvoiceFeatures features={selected.features} labels={featureLabels} />
                : <p className="markdown-error">{labels.noFeatures}</p>}
            </section>
          </div>
        ) : (
          <div className="empty-workspace">
            <span className="empty-icon"><FileText size={30} strokeWidth={1.4} /></span>
            <h2>{labels.emptyTitle}</h2><p>{labels.emptyDescription}</p>
          </div>
        )}
      </main>
    </div>
  )
}
