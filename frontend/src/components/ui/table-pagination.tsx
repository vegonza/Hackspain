import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { useTablePagination } from '@/hooks/useTablePagination'

type Props = { pagination: ReturnType<typeof useTablePagination>['pagination']; loading: boolean }

export function TablePagination({ pagination, loading }: Props) {
  return <nav className="table-pagination" aria-label={pagination.label}>
    {loading ? <Skeleton className="h-4 w-28" /> : <span className="table-pagination-range">{pagination.rangeLabel}</span>}
    <Button variant="outline" size="icon-sm" disabled={loading || pagination.previousDisabled} onClick={pagination.onPrevious} aria-label={pagination.previousLabel}><ChevronLeft size={16} /></Button>
    {loading ? <Skeleton className="h-4 w-12" /> : <span>{pagination.pageLabel}</span>}
    <Button variant="outline" size="icon-sm" disabled={loading || pagination.nextDisabled} onClick={pagination.onNext} aria-label={pagination.nextLabel}><ChevronRight size={16} /></Button>
  </nav>
}
