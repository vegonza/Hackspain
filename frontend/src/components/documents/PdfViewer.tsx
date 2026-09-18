import { Document, Page, pdfjs } from 'react-pdf'
import { DocumentSkeleton } from '@/components/documents/DocumentSkeleton'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import { ZoomIn, ZoomOut } from 'lucide-react'

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()

const options = {
  disableAutoFetch: true,
  disableStream: true,
  cMapUrl: '/pdfjs/cmaps/',
  wasmUrl: '/pdfjs/wasm/',
  iccUrl: '/pdfjs/iccs/',
  standardFontDataUrl: '/pdfjs/standard_fonts/',
}

export function PdfViewer({ documentId }: { documentId: string }) {
  const {
    containerRef, setInner, file, pageWidth, pages, pageCount, currentPage, failed,
    zoom, zoomIn, zoomOut, zoomMin, zoomMax, onLoadSuccess, onPageLoad, onError, labels,
  } = usePdfViewer(documentId)
  return (
    <div className="pdf-viewer">
    <div ref={containerRef} className="pdf-scroll">
      {failed ? <p className="markdown-error" role="alert">{labels.error}</p> : file && pageWidth !== undefined ? (
        <Document file={file} options={options} onLoadSuccess={onLoadSuccess} onLoadError={onError}
          loading={<DocumentSkeleton />} error={<p className="markdown-error">{labels.error}</p>}>
          <div ref={setInner}>
            {pages.map(page => (
              <div key={page.number} ref={page.ref} className="pdf-page" style={{ width: pageWidth, minHeight: pageWidth * page.aspectRatio }}>
                {page.shouldRender && <Page pageNumber={page.number} width={pageWidth} canvasBackground="white"
                  renderTextLayer={false} renderAnnotationLayer={false} onRenderError={onError} onLoadSuccess={onPageLoad}
                  loading={<DocumentSkeleton />} />}
              </div>
            ))}
          </div>
        </Document>
      ) : <DocumentSkeleton />}
    </div>
    {pageCount > 0 && !failed && <div className="pdf-toolbar">
      <button type="button" onClick={zoomOut} disabled={zoom <= zoomMin} aria-label={labels.zoomOut} title={labels.zoomOut}><ZoomOut size={16} /></button>
      <span>{Math.round(zoom * 100)}%</span>
      <button type="button" onClick={zoomIn} disabled={zoom >= zoomMax} aria-label={labels.zoomIn} title={labels.zoomIn}><ZoomIn size={16} /></button>
      <span className="pdf-page-count">{currentPage} / {pageCount}</span>
    </div>}
    </div>
  )
}
