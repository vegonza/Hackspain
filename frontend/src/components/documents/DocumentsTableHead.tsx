import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

type Props = { label: string; icon: LucideIcon; stickyLeft?: boolean }

export function DocumentsTableHead({ label, icon: Icon, stickyLeft = false }: Props) {
  return (
    <th className={cn('sticky top-0 z-20 border-b bg-muted px-2 py-2 text-left text-sm font-medium text-foreground', stickyLeft && 'left-0 z-30')}>
      <div className="flex h-8 items-center gap-1 whitespace-nowrap">
        <Icon className="size-3.5 shrink-0 text-muted-foreground" />
        <span>{label}</span>
      </div>
    </th>
  )
}
