import { Skeleton } from '@/components/ui/skeleton'

export function InvoiceFeaturesSkeleton() {
  return (
    <div className="features-view">
      <dl className="features-grid">
        {Array.from({ length: 11 }, (_, index) => (
          <div key={index}>
            <dt><Skeleton className="h-4 w-16" /></dt>
            <dd><Skeleton className="ml-auto h-[18px] w-3/4" /></dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
