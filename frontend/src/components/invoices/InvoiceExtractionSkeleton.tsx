import { Skeleton } from '@/components/ui/skeleton'

export function InvoiceExtractionSkeleton({ title }: { title: string }) {
  return (
    <section className="invoice-data" aria-label={title} aria-busy="true">
      <div className="extraction-view">
        <dl className="extraction-grid">
          {Array.from({ length: 9 }, (_, index) => (
            <div key={index}>
              <dt><Skeleton className="h-4 w-16" /></dt>
              <dd><Skeleton className="h-4 w-3/4" /></dd>
            </div>
          ))}
          <div className="extraction-line-items">
            <dt><Skeleton className="h-4 w-16" /></dt>
            <dd className="space-y-2"><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-full" /></dd>
          </div>
        </dl>
      </div>
    </section>
  )
}
