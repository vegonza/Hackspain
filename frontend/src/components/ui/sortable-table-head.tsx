import { ChevronDown, ChevronUp, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

interface SortableTableHeadProps<TColumn extends string> {
  column: TColumn
  label: string
  icon: LucideIcon
  activeColumn: TColumn | null
  direction: 'asc' | 'desc'
  onToggle: (column: TColumn) => void
  className?: string
  leading?: ReactNode
}

export function SortableTableHead<TColumn extends string>({
  column,
  label,
  icon: Icon,
  activeColumn,
  direction,
  onToggle,
  className,
  leading,
}: SortableTableHeadProps<TColumn>) {
  const active = activeColumn === column
  return (
    <th aria-sort={active ? direction === 'asc' ? 'ascending' : 'descending' : 'none'} className={cn('px-2 py-2 text-left text-sm font-medium text-foreground', className)}>
      <div className="flex items-center gap-2">
        {leading}
        <button
          type="button"
          onClick={() => onToggle(column)}
          className="group flex h-8 items-center gap-1 whitespace-nowrap"
        >
          <Icon className="size-3.5 shrink-0 text-muted-foreground" />
          <span>{label}</span>
          {active && direction === 'asc' && <ChevronUp className="size-3" />}
          {active && direction === 'desc' && <ChevronDown className="size-3" />}
        </button>
      </div>
    </th>
  )
}
