import { TableToolbar } from '@/components/ui/table-toolbar'
import { Plus, Package, Building2, IdCard, Euro, ListChecks, Calendar } from 'lucide-react'
import { RowActions } from '@/components/ui/row-actions'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { SortableTableHead } from '@/components/ui/sortable-table-head'
import { SearchInput } from '@/components/ui/search-input'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip } from '@/components/ui/tooltip'
import { OrderEditor } from '@/components/orders/OrderEditor'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import type { useOrders } from '@/hooks/useOrders'

const columnIcons = { order_id: Package, supplier_id: Building2, tax_id: IdCard, amount: Euro, status: ListChecks, date: Calendar }

export function OrdersView({ mount, loading, failed, rows, pagination, pageKey, editing, saving, deleting, onDelete, draft, editingId, search,
  sortColumn, sortDirection, onToggleSort, onSearch, onNew, onEdit, onChange, onSave, onCancel, onRetry, labels }: ReturnType<typeof useOrders>) {
  return <section className="invoices-browser" ref={mount} aria-label={labels.title}>
    <TableToolbar pagination={pagination} loading={loading} actions={
      <Button size="sm" className="table-add-button" onClick={onNew} disabled={editing || saving || loading || failed}><Plus size={15} />{labels.add}</Button>
    }>
      <SearchInput value={search} onChange={onSearch} placeholder={labels.search} collapsible={false} />
    </TableToolbar>
    {editing && <OrderEditor {...{ draft, editingId, saving, onChange, onSave, onCancel, labels }} />}
    {failed ? <div role="alert" className="flex items-center gap-3 p-4 text-sm"><span>{labels.failed}</span><Button variant="outline" onClick={onRetry}>{labels.retry}</Button></div>
      : <div className="invoices-table-scroll" key={pageKey}><table className="invoices-table" aria-busy={loading}>
        <colgroup><col style={{ width: 190 }} /><col /><col /><col /><col /><col /><col style={{ width: 88 }} /></colgroup>
        <TableHeader className="[&_tr]:border-b-0"><TableRow className="hover:bg-transparent">
          {(['order_id', 'supplier_id', 'tax_id', 'amount', 'status', 'date'] as const).map(field => <SortableTableHead key={field} column={field} label={labels[field]} icon={columnIcons[field]}
            activeColumn={sortColumn} direction={sortDirection} onToggle={onToggleSort}
            className={`sticky top-0 z-20 border-b bg-muted ${field === 'order_id' ? 'left-0 z-30' : ''}`} />)}
          <TableHead className="sticky top-0 z-20 border-b bg-muted"><span className="sr-only">{labels.actions}</span></TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {loading ? <TableSkeleton /> : rows.map(order => <TableRow key={order.order_id} className="invoice-table-row" data-openable="false">
            {(['order_id', 'supplier_id', 'tax_id'] as const).map(field => <TableCell key={field}>
              <Tooltip text={order[field] ?? ''} onlyWhenTruncated asChild><span className="block truncate">{order[field] ?? '—'}</span></Tooltip>
            </TableCell>)}
            <TableCell className="tabular-nums">{order.displayAmount}</TableCell>
            <TableCell><Badge variant="secondary" className="invoice-table-status">{order.displayStatus}</Badge></TableCell>
            <TableCell className="text-muted-foreground">{order.displayDate}</TableCell>
            <TableCell><RowActions labels={labels} name={order.order_id} disabled={editing || saving || deleting}
              onEdit={() => onEdit(order)} deletion={{ label: labels.delete, confirmation: order.deleteConfirmation, onDelete: () => onDelete(order.order_id) }} /></TableCell>
          </TableRow>)}
          {!loading && rows.length === 0 && <TableRow><TableCell colSpan={7} className="h-40 text-center text-muted-foreground">{labels.empty}</TableCell></TableRow>}
        </TableBody>
      </table></div>}
  </section>
}
