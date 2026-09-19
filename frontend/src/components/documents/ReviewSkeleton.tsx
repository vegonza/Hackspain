import { InvoiceFeaturesSkeleton } from '@/components/documents/InvoiceFeaturesSkeleton'
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
        <div className="pipeline-skeleton"><Skeleton className="h-3 w-20" />{[0, 1, 2].map(index => <Skeleton key={index} className="h-12 w-full" />)}</div>
        <header className="review-header"><Skeleton className="h-3 w-24" /></header>
        <InvoiceFeaturesSkeleton />
      </section>
    </div>
  )
}
