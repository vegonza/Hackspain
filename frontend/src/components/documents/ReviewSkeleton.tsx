import { Skeleton } from '@/components/ui/skeleton'
import { DocumentSkeleton } from '@/components/documents/DocumentSkeleton'

export function ReviewSkeleton({ label }: { label: string }) {
  return (
    <div className="review-desk" role="status" aria-label={label} aria-busy="true">
      <section className="viewer-panel" aria-hidden="true">
        <header className="source-header">
          <Skeleton className="h-3 w-44 max-w-[50%]" />
          <div className="source-tabs items-center">
            <Skeleton className="h-3 w-6" />
            <Skeleton className="h-3 w-14" />
          </div>
        </header>
        <div className="source-body">
          <div className="pdf-viewer">
            <div className="pdf-scroll">
              <div className="pdf-page aspect-[210/297]"><DocumentSkeleton /></div>
            </div>
          </div>
        </div>
      </section>
      <section className="features-panel" aria-hidden="true">
        <header className="review-header"><Skeleton className="h-3 w-24" /></header>
        <div className="features-view">
          <dl className="features-grid">
            <div className="feature-supplier">
              <dt><Skeleton className="h-4 w-16" /></dt>
              <dd><Skeleton className="h-[26px] w-4/5" /></dd>
            </div>
            {Array.from({ length: 8 }, (_, index) => (
              <div key={index}>
                <dt><Skeleton className="h-4 w-16" /></dt>
                <dd><Skeleton className={`ml-auto h-[18px] ${index === 4 ? 'w-full' : 'w-3/4'}`} /></dd>
              </div>
            ))}
            <div className="feature-total-row">
              <dt><Skeleton className="h-4 w-8" /></dt>
              <dd><Skeleton className="ml-auto h-5 w-24" /></dd>
            </div>
            <div className="feature-lines">
              <dt><Skeleton className="h-4 w-16" /></dt>
              <dd><Skeleton className="h-[19px] w-full" /></dd>
            </div>
          </dl>
        </div>
      </section>
    </div>
  )
}
