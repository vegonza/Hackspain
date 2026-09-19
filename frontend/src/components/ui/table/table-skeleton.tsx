import { Skeleton } from '@/components/ui/skeleton'
import { TableRow, TableCell } from '@/components/ui/table'
import { TABLE_PAGE_SIZE } from '@/hooks/tablePagination'

export function TableSkeleton({ columns = 7 }: { columns?: number }) {
  return <>{Array.from({ length: TABLE_PAGE_SIZE }, (_, row) => <TableRow key={row} className="invoice-table-row" data-openable="false" aria-hidden="true">
    {Array.from({ length: columns }, (_, column) => <TableCell key={column}><Skeleton className="h-4 w-full" /></TableCell>)}
  </TableRow>)}</>
}
