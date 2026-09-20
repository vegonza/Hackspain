import { Plus, Users, IdCard, MapPin, Mail } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/search-input'
import { TableToolbar } from '@/components/ui/table-toolbar'
import { SortableTableHead } from '@/components/ui/sortable-table-head'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { ClientEditor } from '@/components/clients/ClientEditor'
import { RowActions } from '@/components/ui/row-actions'
import type { useClients } from '@/hooks/useClients'

const icons = { name: Users, tax_id: IdCard, address: MapPin, email: Mail }
export function ClientsView({ mount, ...c }: ReturnType<typeof useClients>) {
  return <section className="invoices-browser" ref={mount} key={c.reload} aria-label={c.labels.title}>
    <TableToolbar pagination={c.pagination} loading={c.loading} actions={<Button size="sm" className="table-add-button" disabled={c.editing || c.saving || c.deleting || c.loading || c.failed} onClick={c.onNew}><Plus size={15} />{c.labels.add}</Button>}>
      <SearchInput value={c.search} onChange={c.onSearch} placeholder={c.labels.search} collapsible={false} />
    </TableToolbar>
    {c.editing && <ClientEditor {...c} />}
    {c.failed ? <div role="alert" className="flex items-center gap-3 p-4 text-sm"><span>{c.labels.failed}</span><Button variant="outline" onClick={c.onRetry}>{c.labels.retry}</Button></div> : <div className="invoices-table-scroll" key={c.pageKey}>
      <table className="invoices-table" aria-busy={c.loading}>
        <colgroup><col style={{ width: '30%' }} /><col style={{ width: 150 }} /><col /><col style={{ width: '25%' }} /><col style={{ width: 88 }} /></colgroup>
        <TableHeader className="[&_tr]:border-b-0"><TableRow className="hover:bg-transparent">{(['name', 'tax_id', 'address', 'email'] as const).map(field => <SortableTableHead key={field} column={field} label={c.labels[field]} icon={icons[field]} activeColumn={c.sortColumn} direction={c.sortDirection} onToggle={c.onToggleSort} className={`sticky top-0 z-20 border-b bg-muted ${field === 'name' ? 'left-0 z-30' : ''}`} />)}<TableHead className="sticky top-0 z-20 border-b bg-muted"><span className="sr-only">{c.labels.actions}</span></TableHead></TableRow></TableHeader>
        <TableBody>{c.loading ? <TableSkeleton columns={5} /> : c.rows.map(client => <TableRow key={client.id} className="invoice-table-row" data-openable="false">
          <TableCell><div className="flex min-w-0 items-center gap-3">{client.logo_url !== '' && <img src={client.logo_url} alt="" className="size-6 shrink-0 object-contain" />}<Tooltip text={client.name} onlyWhenTruncated asChild><span className="block truncate">{client.name}</span></Tooltip></div></TableCell>
          {(['tax_id', 'address', 'email'] as const).map(field => <TableCell key={field}><Tooltip text={client[field]} onlyWhenTruncated asChild><span className="block truncate">{client[field]}</span></Tooltip></TableCell>)}
          <TableCell><RowActions labels={c.labels} name={client.name} disabled={c.editing || c.saving || c.deleting} onEdit={() => c.onEdit(client)} deletion={{ label: c.labels.delete, confirmation: client.deleteConfirmation, onDelete: () => c.onDelete(client.id) }} /></TableCell>
        </TableRow>)}{!c.loading && c.rows.length === 0 && <TableRow><TableCell colSpan={5} className="h-40 text-center text-muted-foreground">{c.labels.empty}</TableCell></TableRow>}</TableBody>
      </table>
    </div>}
  </section>
}
