import { Building2, CircleAlert, Clock, Euro, IdCard, Hash, ListChecks, Package, RefreshCw } from 'lucide-react'
import { TableToolbar } from '@/components/ui/table-toolbar'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { SearchInput } from '@/components/ui/search-input'
import { SortableTableHead } from '@/components/ui/sortable-table-head'
import { TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { useErpSnapshot } from '@/hooks/useErpSnapshot'

type Props = Pick<ReturnType<typeof useErpSnapshot>, 'onRefresh' | 'refreshing' | 'loading' | 'failed' | 'rows' | 'pagination' | 'pageKey' | 'search' | 'onSearch' | 'sortColumn' | 'sortDirection' | 'onToggleSort' | 'onSelect' | 'onEntryLink' | 'labels'>

export function ErpTable({ onRefresh, refreshing, loading, failed, rows, pagination, pageKey, search, onSearch, sortColumn, sortDirection, onToggleSort, onSelect, onEntryLink, labels }: Props) {
  const columns = [
    { column: 'entry', label: labels.entry, icon: Hash, width: '220px' },
    { column: 'order', label: labels.order, icon: Package, width: '150px' },
    { column: 'supplier', label: labels.supplier, icon: Building2, width: '120px' },
    { column: 'taxId', label: labels.taxId, icon: IdCard, width: '140px' },
    { column: 'status', label: labels.status, icon: ListChecks, width: '130px' },
    { column: 'date', label: labels.date, icon: Clock, width: '150px' },
    { column: 'amount', label: labels.amount, icon: Euro, width: '150px' },
    { column: 'warnings', label: labels.warnings, icon: CircleAlert, width: '110px' },
  ] as const
  return (
    <>
      <TableToolbar pagination={pagination} loading={loading} actions={
        <Button size="sm" className="table-add-button" onClick={onRefresh} disabled={loading || refreshing} aria-busy={refreshing}>
          <RefreshCw className={cn('size-3.5', refreshing && 'animate-spin')} />
          {refreshing ? labels.refreshing : labels.refresh}
        </Button>
      }>
        <SearchInput value={search} onChange={onSearch} placeholder={labels.search} collapsible={false} />
      </TableToolbar>
      <div className="invoices-table-scroll" key={pageKey}>
        <table className="invoices-table" style={{ minWidth: 1170 }} aria-busy={loading}>
          <colgroup>{columns.map(column => <col key={column.column} style={{ width: column.width }} />)}</colgroup>
          <TableHeader className="[&_tr]:border-b-0"><TableRow className="hover:bg-transparent">
            {columns.map(column => <SortableTableHead key={column.column} column={column.column} label={column.label} icon={column.icon}
              activeColumn={sortColumn} direction={sortDirection} onToggle={onToggleSort}
              className={cn('sticky top-0 z-20 border-b bg-muted', column.column === 'entry' && 'left-0 z-30')} />)}
          </TableRow></TableHeader>
          <TableBody>
            {rows.map(row => <TableRow key={row.id} className="invoice-table-row" data-openable="true" onClick={() => onSelect(row.id)}>
              <TableCell><Tooltip text={row.entryId} onlyWhenTruncated asChild><a className="invoice-table-name" href={row.href} onClick={onEntryLink}>{row.entryId}</a></Tooltip></TableCell>
              <TableCell>{row.orderId}</TableCell>
              <TableCell>{row.supplierId}</TableCell>
              <TableCell>{row.taxId}</TableCell>
              <TableCell><Badge variant="secondary" className="invoice-table-status">{row.statusLabel}</Badge></TableCell>
              <TableCell className="text-muted-foreground">{row.dateLabel}</TableCell>
              <TableCell><span className="tabular-nums">{row.amountLabel}</span></TableCell>
              <TableCell>{row.warningLabels.length === 0 ? <span className="text-muted-foreground">—</span>
                : <Tooltip text={row.warningLabels.join('; ')} asChild><Badge variant="destructive" className="invoice-table-status"><CircleAlert size={13} />{row.warningLabels.length}</Badge></Tooltip>}</TableCell>
            </TableRow>)}
            {loading && <TableSkeleton columns={columns.length} />}
            {!loading && !failed && rows.length === 0 && <TableRow className="hover:bg-transparent"><TableCell colSpan={columns.length} className="h-40 text-center text-muted-foreground">{search.trim() ? labels.noResults : labels.emptySnapshot}</TableCell></TableRow>}
          </TableBody>
        </table>
      </div>
    </>
  )
}
