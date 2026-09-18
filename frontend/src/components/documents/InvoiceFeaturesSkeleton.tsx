import { Skeleton } from '@/components/ui/skeleton'

export function InvoiceFeaturesSkeleton() {
  return (
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
  )
}
