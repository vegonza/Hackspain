import { Skeleton } from '@/components/ui/skeleton'
import { TableRow, TableCell } from '@/components/ui/table'

export function TableSkeleton({ columns = 7 }: { columns?: number }) {
  return <>{Array.from({ length: 6 }, (_, row) => <TableRow key={row} className="invoice-table-row" data-openable="false">
    {Array.from({ length: columns }, (_, column) => <TableCell key={column}><Skeleton className="h-4 w-full" /></TableCell>)}
  </TableRow>)}</>
}
