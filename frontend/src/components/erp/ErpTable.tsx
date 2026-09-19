import { Building2, CircleAlert, Clock, Euro, Fingerprint, Hash, ListChecks, Package } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { SearchInput } from '@/components/ui/search-input'
import { SortableTableHead } from '@/components/ui/sortable-table-head'
import { TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { useErpSnapshot } from '@/hooks/useErpSnapshot'

type Props = Pick<ReturnType<typeof useErpSnapshot>, 'loading' | 'failed' | 'rows' | 'summary' | 'search' | 'onSearch' | 'sortColumn' | 'sortDirection' | 'onToggleSort' | 'onSelect' | 'onEntryLink' | 'labels'>

export function ErpTable({ loading, failed, rows, summary, search, onSearch, sortColumn, sortDirection, onToggleSort, onSelect, onEntryLink, labels }: Props) {
  const columns = [
    { column: 'entry', label: labels.entry, icon: Hash, width: undefined },
    { column: 'order', label: labels.order, icon: Package, width: '150px' },
    { column: 'supplier', label: labels.supplier, icon: Building2, width: '120px' },
    { column: 'taxId', label: labels.taxId, icon: Fingerprint, width: '140px' },
    { column: 'status', label: labels.status, icon: ListChecks, width: '130px' },
    { column: 'date', label: labels.date, icon: Clock, width: '150px' },
    { column: 'amount', label: labels.amount, icon: Euro, width: '150px' },
    { column: 'warnings', label: labels.warnings, icon: CircleAlert, width: '110px' },
  ] as const
  return (
    <>
      <header className="documents-toolbar">
        <SearchInput value={search} onChange={onSearch} placeholder={labels.search} collapsible={false} />
        {summary !== null && <span className="ml-auto truncate text-sm text-muted-foreground">{summary}</span>}
      </header>
      <div className="documents-table-scroll">
        <table className="documents-table" aria-busy={loading}>
          <colgroup>{columns.map(column => <col key={column.column} style={column.width === undefined ? undefined : { width: column.width }} />)}</colgroup>
          <TableHeader className="[&_tr]:border-b-0"><TableRow className="hover:bg-transparent">
            {columns.map(column => <SortableTableHead key={column.column} column={column.column} label={column.label} icon={column.icon}
              activeColumn={sortColumn} direction={sortDirection} onToggle={onToggleSort}
              className={cn('sticky top-0 z-20 border-b bg-muted', column.column === 'entry' && 'left-0 z-30')} />)}
          </TableRow></TableHeader>
          <TableBody>
            {rows.map(row => <TableRow key={row.id} className="document-table-row" data-openable="true" onClick={() => onSelect(row.id)}>
              <TableCell><Tooltip text={row.entryId} onlyWhenTruncated asChild><a className="document-table-name" href={row.href} onClick={onEntryLink}>{row.entryId}</a></Tooltip></TableCell>
              <TableCell>{row.orderId}</TableCell>
              <TableCell>{row.supplierId}</TableCell>
              <TableCell>{row.taxId}</TableCell>
              <TableCell><Badge variant="secondary" className="document-table-status">{row.statusLabel}</Badge></TableCell>
              <TableCell className="text-muted-foreground">{row.dateLabel}</TableCell>
              <TableCell><span className="tabular-nums">{row.amountLabel}</span></TableCell>
              <TableCell>{row.warningLabels.length === 0 ? <span className="text-muted-foreground">—</span>
                : <Tooltip text={row.warningLabels.join('; ')} asChild><Badge variant="destructive" className="document-table-status"><CircleAlert size={13} />{row.warningLabels.length}</Badge></Tooltip>}</TableCell>
            </TableRow>)}
            {loading && <TableSkeleton columns={columns.length} />}
            {!loading && !failed && rows.length === 0 && <TableRow className="hover:bg-transparent"><TableCell colSpan={columns.length} className="h-40 text-center text-muted-foreground">{search.trim() ? labels.noResults : labels.emptySnapshot}</TableCell></TableRow>}
          </TableBody>
        </table>
      </div>
    </>
  )
}
