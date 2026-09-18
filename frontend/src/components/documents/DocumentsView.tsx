import { FileText, Upload } from 'lucide-react'
import logo from '@/assets/logo.jpeg'
import type { useDocuments } from '@/hooks/useDocuments'
import { DocumentSkeleton } from '@/components/documents/DocumentSkeleton'
import { Markdown } from '@/components/documents/Markdown'
import { HoldButton } from '@/components/ui/hold-button'
import { PdfViewer } from '@/components/documents/PdfViewer'

type Props = ReturnType<typeof useDocuments>

export function DocumentsView({ documents, selected, selectedId, loading, uploading, deleting, onUpload, onDelete, onSelect, labels }: Props) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><img src={logo} alt={labels.appName} /></div>
        <label className={`upload-button ${uploading ? 'disabled' : ''}`}>
          <Upload size={16} />{uploading ? labels.uploading : labels.upload}
          <input type="file" accept="application/pdf,.pdf" onChange={onUpload} disabled={uploading || deleting} aria-label={labels.upload} />
        </label>
        <div className="library-label">{labels.library}<span>{documents.length}</span></div>
        <nav className="document-list" aria-label={labels.library}>
          {documents.length === 0 && <p className="empty-list">{labels.emptyList}</p>}
          {documents.map(document => (
            <button key={document.id} className="document-item" aria-current={selectedId === document.id ? 'true' : undefined}
              disabled={uploading || deleting} onClick={() => void onSelect(document.id)}>
              <FileText size={17} />
              <span className="document-name" title={document.name}>{document.name}</span>
              {document.status === 'error' && <span className="error-dot" title={labels.error} aria-label={labels.error} />}
            </button>
          ))}
        </nav>
      </aside>
      <main className="workspace">
        <header className="workspace-header">
          <div><span className="eyebrow">{labels.title}</span><h1>{selected ? selected.name : labels.library}</h1></div>
          {selected && <div className="document-actions">
            {selected.status === 'ready' && <span className="page-count">{labels.pages}</span>}
            <HoldButton key={selectedId} label={deleting ? labels.deleting : labels.delete}
              disabled={loading || uploading || deleting} onConfirm={onDelete} />
          </div>}
        </header>
        {loading || uploading ? (
          <div className="loading-workspace" role="status">
            <p>{uploading ? labels.uploading : labels.loading}</p>
            <div className="viewer-grid"><DocumentSkeleton /><DocumentSkeleton /></div>
          </div>
        ) : selected ? (
          <div className="viewer-grid">
            <section className="viewer-panel">
              <div className="panel-heading">{labels.pdf}</div>
              <PdfViewer key={selected.id} documentId={selected.id} />
            </section>
            <section className="viewer-panel">
              <div className="panel-heading">{labels.markdown}</div>
              <div className="markdown-scroll">
                {selected.status === 'ready' ? <Markdown content={selected.markdown} /> : <p className="markdown-error">{labels.noMarkdown}</p>}
              </div>
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
