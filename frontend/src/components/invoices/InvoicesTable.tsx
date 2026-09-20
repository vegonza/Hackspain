import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { InvoiceBillingHeader } from '@/components/invoices/InvoiceBillingHeader'
import { InvoiceBillingSection } from '@/components/invoices/InvoiceBillingSection'
import { InvoiceBillingRow } from '@/components/invoices/InvoiceBillingRow'
import { InvoiceActionsMenu } from '@/components/invoices/InvoiceActionsMenu'
import type { useInvoices } from '@/hooks/useInvoices'
import type { useInvoiceTable } from '@/hooks/useInvoiceTable'

export type InvoicesTableProps = Pick<ReturnType<typeof useInvoices>, 'invoicesLoading' | 'onUpload' | 'onSelect' | 'onInvoiceLink' | 'onDelete' | 'deleting' | 'onRedo'> & {
  issued: ReturnType<typeof useInvoices>['issued']
  issuedList: ReturnType<typeof useInvoices>['issuedList']
  table: ReturnType<typeof useInvoiceTable>
  redoDisabled: boolean
}

export function InvoicesTable({ issued, issuedList, invoicesLoading, onUpload, table: { mountMonthShortcuts, ...table }, onSelect, onInvoiceLink, onDelete, deleting, onRedo, redoDisabled }: InvoicesTableProps) {
  return <section ref={mountMonthShortcuts} className="invoices-browser billing-browser" aria-label={table.labels.title}>
    <InvoiceBillingHeader table={table} loading={invoicesLoading || issued.loading} failed={issued.failed} onUpload={onUpload} />
    <div className="invoices-table-scroll" key={table.period}>
      <InvoiceBillingSection title={issuedList.labels.received} labels={{ party: table.labels.supplier, status: table.labels.review, date: table.labels.date, amount: table.labels.amount, gross: table.labels.gross, actions: table.labels.actions }}
        sort={table.sort} onSort={table.onSort} loading={invoicesLoading} empty={table.rows.length === 0} emptyMessage={table.emptyMessage} error={null}
        tools={<dl className="billing-summary billing-received-summary">{table.receivedSummaries.map(summary => <div key={summary.value} data-summary={summary.value}><dt>{summary.label}</dt><dd><Tooltip text={summary.description} asChild><span>{invoicesLoading ? <Skeleton className="h-4 w-20" /> : summary.amount}{!invoicesLoading && summary.incomplete && <span className="billing-incomplete">*</span>}</span></Tooltip></dd></div>)}</dl>}>
        {table.rows.map(invoice => <InvoiceBillingRow key={invoice.id} invoice={invoice} onSelect={onSelect} onInvoiceLink={onInvoiceLink}
          actions={<InvoiceActionsMenu labels={table.labels} downloadDisabled={!invoice.canOpen || table.downloading !== null} downloading={table.downloading === invoice.id}
            onDownload={() => table.onDownload(invoice.id)} management={{
              redoLabel: table.labels.redo, deleteLabel: table.labels.delete,
              redoConfirmation: invoice.redoConfirmation, deleteConfirmation: invoice.deleteConfirmation,
              redoDisabled: redoDisabled || !invoice.canManage, deleteDisabled: deleting || !invoice.canManage,
              onRedo: () => void onRedo(invoice.id), onDelete: () => void onDelete(invoice.id),
            }} />} />)}
      </InvoiceBillingSection>
      <InvoiceBillingSection title={issuedList.labels.title} labels={{ party: issuedList.labels.client, status: issuedList.labels.status, date: table.labels.date, amount: table.labels.amount, gross: table.labels.gross, actions: table.labels.actions }}
        sort={table.sort} onSort={table.onSort} loading={issued.loading} empty={issuedList.rows.length === 0} emptyMessage={issuedList.labels.empty}
        error={issued.failed ? issuedList.labels.failed : null}
        tools={<Button variant="ghost" size="sm" onClick={issuedList.onCreate}><Plus size={15} />{issuedList.labels.create}</Button>}>
        {issuedList.rows.map(invoice => <InvoiceBillingRow key={invoice.id} invoice={invoice} onSelect={issuedList.onOpen} onInvoiceLink={issuedList.onNavigate}
          actions={<InvoiceActionsMenu labels={issuedList.labels} management={null} downloadDisabled={!invoice.canDownload || issuedList.downloading !== null} downloading={issuedList.downloading === invoice.id} onDownload={invoice.onDownload} />} />)}
      </InvoiceBillingSection>
    </div>
  </section>
}
