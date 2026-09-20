import { Ellipsis } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TableCell, TableRow } from '@/components/ui/table'
import { TABLE_PAGE_SIZE } from '@/hooks/tablePagination'

export function InvoiceBillingSkeleton({ actions, gross }: { actions: string; gross: string }) {
  return <>{Array.from({ length: TABLE_PAGE_SIZE }, (_, index) => <TableRow key={index} className="invoice-table-row billing-row" data-openable="false" aria-hidden="true">
    <TableCell><div className="billing-identity">
      <Skeleton className="size-9 shrink-0" />
      <div className="billing-identity-text space-y-1"><Skeleton className="h-3.5 w-2/5" /><Skeleton className="h-3 w-3/4" /></div>
    </div></TableCell>
    <TableCell><Skeleton className="h-5 w-28 rounded-full" /></TableCell>
    <TableCell className="billing-date"><Skeleton className="h-3.5 w-20" /></TableCell>
    <TableCell className="billing-money"><Skeleton className="ml-auto h-3.5 w-20" /><div className="mt-1 flex items-center justify-end gap-1 text-[11px] text-muted-foreground">{gross}<Skeleton className="h-3 w-16" /></div></TableCell>
    <TableCell><div className="invoice-table-action"><Button variant="ghost" size="icon-sm" disabled tabIndex={-1} aria-label={actions}><Ellipsis size={16} /></Button></div></TableCell>
  </TableRow>)}</>
}
