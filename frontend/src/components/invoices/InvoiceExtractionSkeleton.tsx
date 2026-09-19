import { Skeleton } from '@/components/ui/skeleton'

export function InvoiceExtractionSkeleton({ title }: { title: string }) {
  return (
    <section className="invoice-data" aria-label={title} aria-busy="true">
      <div className="extraction-view">
        <dl className="extraction-grid">
          {Array.from({ length: 11 }, (_, index) => (
            <div key={index}>
              <dt><Skeleton className="h-4 w-16" /></dt>
              <dd><Skeleton className="ml-auto h-[18px] w-3/4" /></dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}
