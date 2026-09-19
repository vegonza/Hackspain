import type { LucideIcon } from 'lucide-react'
import type { InvoiceSortColumn } from '@/hooks/useInvoices'
import { SortableTableHead } from '@/components/ui/sortable-table-head'
import { cn } from '@/lib/utils'

type Props = {
  label: string
  icon: LucideIcon
  stickyLeft?: boolean
  column: InvoiceSortColumn
  sortColumn: InvoiceSortColumn | null
  sortDirection: 'asc' | 'desc'
  onToggleSort: (column: InvoiceSortColumn) => void
}

export function InvoicesTableHead({ label, icon, stickyLeft = false, column, sortColumn, sortDirection, onToggleSort }: Props) {
  return <SortableTableHead column={column} label={label} icon={icon} activeColumn={sortColumn} direction={sortDirection} onToggle={onToggleSort}
    className={cn('sticky top-0 z-20 border-b bg-muted', stickyLeft && 'left-0 z-30')} />
}
