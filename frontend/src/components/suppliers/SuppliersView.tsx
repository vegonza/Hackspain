import { Pencil, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/search-input'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip } from '@/components/ui/tooltip'
import { SupplierEditor } from '@/components/suppliers/SupplierEditor'
import { SuppliersSkeleton } from '@/components/suppliers/SuppliersSkeleton'
import type { useSuppliers } from '@/hooks/useSuppliers'

export function SuppliersView({ mount, loading, failed, rows, editing, saving, draft, editingId, search,
  onSearch, onNew, onEdit, onChange, onSave, onCancel, onRetry, labels }: ReturnType<typeof useSuppliers>) {
  return <section className="documents-browser" ref={mount} aria-label={labels.title}>
    <header className="documents-toolbar">
      <SearchInput value={search} onChange={onSearch} placeholder={labels.search} collapsible={false} />
      <Button className="ml-auto shrink-0" onClick={onNew} disabled={editing || loading || failed}><Plus size={15} />{labels.add}</Button>
    </header>
    {editing && <SupplierEditor {...{ draft, editingId, saving, onChange, onSave, onCancel, labels }} />}
    {failed ? <div role="alert" className="flex items-center gap-3 p-4 text-sm"><span>{labels.failed}</span><Button variant="outline" onClick={onRetry}>{labels.retry}</Button></div>
      : <div className="documents-table-scroll"><table className="documents-table" aria-busy={loading}>
        <colgroup><col style={{ width: 95 }} /><col /><col style={{ width: 125 }} /><col style={{ width: 270 }} /><col style={{ width: 140 }} /><col style={{ width: 165 }} /><col style={{ width: 48 }} /></colgroup>
        <TableHeader><TableRow className="hover:bg-transparent">
          {(['supplier_id', 'legal_name', 'tax_id', 'iban', 'city', 'payment_terms_days'] as const).map(field => <TableHead key={field} className="sticky top-0 bg-muted">{labels[field]}</TableHead>)}
          <TableHead className="sticky top-0 bg-muted"><span className="sr-only">{labels.edit}</span></TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {loading ? <SuppliersSkeleton /> : rows.map(supplier => <TableRow key={supplier.supplier_id}>
            {(['supplier_id', 'legal_name', 'tax_id', 'iban', 'city'] as const).map(field => <TableCell key={field}>
              <Tooltip text={supplier[field]} onlyWhenTruncated asChild><span className="block truncate">{supplier[field]}</span></Tooltip>
            </TableCell>)}
            <TableCell className="tabular-nums">{supplier.payment_terms_days} {labels.days}</TableCell>
            <TableCell><Button variant="ghost" size="icon-sm" disabled={editing} aria-label={`${labels.edit}: ${supplier.legal_name}`} onClick={() => onEdit(supplier)}><Pencil size={14} /></Button></TableCell>
          </TableRow>)}
          {!loading && rows.length === 0 && <TableRow><TableCell colSpan={7} className="h-40 text-center text-muted-foreground">{labels.empty}</TableCell></TableRow>}
        </TableBody>
      </table></div>}
  </section>
}
