import { Skeleton } from '@/components/ui/skeleton'

export function InvoiceSkeleton() {
  return (
    <div className="invoice-skeleton" aria-busy="true">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="mt-8 h-4 w-3/4" />
      <Skeleton className="mt-3 h-4 w-full" />
      <Skeleton className="mt-3 h-4 w-5/6" />
      <Skeleton className="mt-8 h-40 w-full" />
      <Skeleton className="mt-8 h-4 w-2/3" />
      <Skeleton className="mt-3 h-4 w-full" />
    </div>
  )
}
