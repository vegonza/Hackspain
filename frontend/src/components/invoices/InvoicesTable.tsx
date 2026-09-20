import { Building2, CalendarDays, Euro } from 'lucide-react'
import { InvoiceBillingHeader } from '@/components/invoices/InvoiceBillingHeader'
import { InvoiceBillingRow } from '@/components/invoices/InvoiceBillingRow'
import { SortableTableHead } from '@/components/ui/sortable-table-head'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import type { useInvoices } from '@/hooks/useInvoices'
import type { useInvoiceTable } from '@/hooks/useInvoiceTable'

export type InvoicesTableProps = Pick<ReturnType<typeof useInvoices>, 'invoicesLoading' | 'onUpload' | 'onSelect' | 'onInvoiceLink' | 'onDelete' | 'deleting' | 'onRedo'> & {
  table: ReturnType<typeof useInvoiceTable>
  redoDisabled: boolean
}

export function InvoicesTable({ invoicesLoading, onUpload, table: { mountMonthShortcuts, ...table }, onSelect, onInvoiceLink, onDelete, deleting, onRedo, redoDisabled }: InvoicesTableProps) {
  return <section ref={mountMonthShortcuts} className="invoices-browser billing-browser" aria-label={table.labels.title}>
    <InvoiceBillingHeader table={table} loading={invoicesLoading} onUpload={onUpload} />
    <div className="invoices-table-scroll" key={table.period}>
      <table className="invoices-table billing-table" aria-busy={invoicesLoading}>
        <colgroup><col /><col className="billing-review-column" /><col style={{ width: '104px' }} /><col style={{ width: '160px' }} /><col style={{ width: '52px' }} /></colgroup>
        <TableHeader><TableRow className="hover:bg-transparent">
          <SortableTableHead column="supplier" label={table.labels.supplier} icon={Building2} activeColumn={table.sort.column} direction={table.sort.direction} onToggle={table.onSort} />
          <TableHead>{table.labels.review}</TableHead>
          <SortableTableHead column="date" label={table.labels.date} icon={CalendarDays} activeColumn={table.sort.column} direction={table.sort.direction} onToggle={table.onSort} />
          <SortableTableHead column="amount" label={table.labels.amount} icon={Euro} activeColumn={table.sort.column} direction={table.sort.direction} onToggle={table.onSort} className="billing-money-head" />
          <TableHead><span className="sr-only">{table.labels.actions}</span></TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {invoicesLoading ? <TableSkeleton columns={5} /> : table.rows.map(invoice => <InvoiceBillingRow key={invoice.id} invoice={invoice} labels={table.labels}
            downloading={table.downloading} onDownload={table.onDownload} onSelect={onSelect} onInvoiceLink={onInvoiceLink}
            onRedo={onRedo} onDelete={onDelete} deleting={deleting} redoDisabled={redoDisabled} />)}
          {!invoicesLoading && table.rows.length === 0 && <TableRow className="hover:bg-transparent"><TableCell colSpan={5} className="h-48 text-center text-muted-foreground">{table.emptyMessage}</TableCell></TableRow>}
        </TableBody>
      </table>
    </div>
  </section>
}
