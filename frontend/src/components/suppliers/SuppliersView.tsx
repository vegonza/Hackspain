import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Hash, Building2, IdCard, Landmark, MapPin, Clock } from 'lucide-react'
import { RowActions } from '@/components/ui/row-actions'
import { Button } from '@/components/ui/button'
import { SortableTableHead } from '@/components/ui/sortable-table-head'
import { SearchInput } from '@/components/ui/search-input'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip } from '@/components/ui/tooltip'
import { SupplierEditor } from '@/components/suppliers/SupplierEditor'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import type { useSuppliers } from '@/hooks/useSuppliers'

const columnIcons = { supplier_id: Hash, legal_name: Building2, tax_id: IdCard, iban: Landmark, city: MapPin, payment_terms_days: Clock }

export function SuppliersView({ mount, loading, failed, rows, editing, saving, deleting, onDelete, draft, editingId, search,
  sortColumn, sortDirection, onToggleSort, onSearch, onNew, onEdit, onChange, onSave, onCancel, onRetry, labels }: ReturnType<typeof useSuppliers>) {
  return <section className="documents-browser" ref={mount} aria-label={labels.title}>
    <header className="documents-toolbar">
      <SearchInput value={search} onChange={onSearch} placeholder={labels.search} collapsible={false} />
      {loading ? <Skeleton className="h-4 w-24 shrink-0" /> : !failed && <span className="shrink-0 text-sm text-muted-foreground">{labels.count}</span>}
      <Button size="sm" className="table-add-button" onClick={onNew} disabled={editing || loading || failed}><Plus size={15} />{labels.add}</Button>
    </header>
    {editing && <SupplierEditor {...{ draft, editingId, saving, onChange, onSave, onCancel, labels }} />}
    {failed ? <div role="alert" className="flex items-center gap-3 p-4 text-sm"><span>{labels.failed}</span><Button variant="outline" onClick={onRetry}>{labels.retry}</Button></div>
      : <div className="documents-table-scroll"><table className="documents-table" aria-busy={loading}>
        <colgroup><col style={{ width: 95 }} /><col /><col style={{ width: 125 }} /><col style={{ width: 270 }} /><col style={{ width: 140 }} /><col style={{ width: 165 }} /><col style={{ width: 48 }} /></colgroup>
        <TableHeader className="[&_tr]:border-b-0"><TableRow className="hover:bg-transparent">
          {(['supplier_id', 'legal_name', 'tax_id', 'iban', 'city', 'payment_terms_days'] as const).map(field => <SortableTableHead key={field} column={field} label={labels[field]} icon={columnIcons[field]}
            activeColumn={sortColumn} direction={sortDirection} onToggle={onToggleSort}
            className={`sticky top-0 z-20 border-b bg-muted ${field === 'supplier_id' ? 'left-0 z-30' : ''}`} />)}
          <TableHead className="sticky top-0 z-20 border-b bg-muted"><span className="sr-only">{labels.actions}</span></TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {loading ? <TableSkeleton /> : rows.map(supplier => <TableRow key={supplier.supplier_id} className="document-table-row" data-openable="false">
            {(['supplier_id', 'legal_name', 'tax_id', 'iban', 'city'] as const).map(field => <TableCell key={field}>
              <Tooltip text={supplier[field]} onlyWhenTruncated asChild><span className="block truncate">{supplier[field]}</span></Tooltip>
            </TableCell>)}
            <TableCell className="tabular-nums">{supplier.payment_terms_days} {labels.days}</TableCell>
            <TableCell><RowActions labels={labels} name={supplier.supplier_id} disabled={editing || saving || deleting}
              onEdit={() => onEdit(supplier)} onDelete={() => onDelete(supplier.supplier_id)} /></TableCell>
          </TableRow>)}
          {!loading && rows.length === 0 && <TableRow><TableCell colSpan={7} className="h-40 text-center text-muted-foreground">{labels.empty}</TableCell></TableRow>}
        </TableBody>
      </table></div>}
  </section>
}
