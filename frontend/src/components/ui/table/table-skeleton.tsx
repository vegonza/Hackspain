import { Skeleton } from '@/components/ui/skeleton'
import { TableRow, TableCell } from '@/components/ui/table'

export function TableSkeleton() {
  return <>{Array.from({ length: 6 }, (_, row) => <TableRow key={row} className="document-table-row" data-openable="false">
    {Array.from({ length: 7 }, (_, column) => <TableCell key={column}><Skeleton className="h-4 w-full" /></TableCell>)}
  </TableRow>)}</>
}
