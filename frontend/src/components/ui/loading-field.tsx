import type { ReactNode } from 'react'
import { Skeleton } from '@/components/ui/skeleton'

export function LoadingField({ loading, children }: { loading: boolean; children: ReactNode }) {
  return <div className="loading-field relative" aria-busy={loading} data-loading={loading}>
    {children}
    {loading && <Skeleton className="pointer-events-none absolute left-3 top-2 h-4 w-1/2" aria-hidden="true" />}
  </div>
}
