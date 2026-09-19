import type { ComponentProps, ReactNode } from 'react'
import { TablePagination } from '@/components/ui/table-pagination'

type Props = ComponentProps<typeof TablePagination> & { children: ReactNode; actions?: ReactNode }

export function TableToolbar({ children, actions, pagination, loading }: Props) {
  return <header className="table-toolbar">
    <div className="table-toolbar-content">{children}</div>
    <div className="table-toolbar-controls">
      <TablePagination pagination={pagination} loading={loading} />
      {actions}
    </div>
  </header>
}
