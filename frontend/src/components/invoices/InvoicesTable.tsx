import { InvoiceDecisionBadge } from '@/components/invoices/InvoiceDecisionBadge'
import { TableToolbar } from '@/components/ui/table-toolbar'
import type { useInvoiceTable } from '@/hooks/useInvoiceTable'
import { InvoicesTableHead } from '@/components/invoices/InvoicesTableHead'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { CircleAlert, Timer, DollarSign, Clock, FileText, ListChecks, LoaderCircle, Upload, RotateCcw, Trash2 } from 'lucide-react'
import type { useInvoices } from '@/hooks/useInvoices'
import { SearchInput } from '@/components/ui/search-input'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip } from '@/components/ui/tooltip'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'

export type InvoicesTableProps = Pick<ReturnType<typeof useInvoices>, 'invoicesLoading' | 'sortColumn' | 'sortDirection' | 'onToggleSort' | 'onUpload' | 'search' | 'onSearch' | 'onSelect' | 'onInvoiceLink' | 'onDelete' | 'deleting' | 'labels'> & {
  table: ReturnType<typeof useInvoiceTable>
  onRedo: ReturnType<typeof useInvoices>['onRedo']
  redoDisabled: boolean
}

export function InvoicesTable({ invoicesLoading, sortColumn, sortDirection, onToggleSort, onUpload, table: { rows, pagination, pageKey }, search, onSearch, onSelect, onInvoiceLink, onDelete, deleting, labels, onRedo, redoDisabled }: InvoicesTableProps) {
  return (
    <section className="invoices-browser" aria-label={labels.library}>
      <TableToolbar pagination={pagination} loading={invoicesLoading} actions={
        <Button asChild size="sm" className="table-add-button"><label className="upload-button">
          <Upload size={15} />{labels.upload}
          <input type="file" accept="application/pdf,.pdf" multiple onChange={onUpload} aria-label={labels.upload} />
        </label></Button>
      }>
        <SearchInput value={search} onChange={onSearch} placeholder={labels.search} collapsible={false} />
      </TableToolbar>
      <div className="invoices-table-scroll" key={pageKey}>
        <table className="invoices-table invoices-list-table" aria-busy={invoicesLoading}>
          <colgroup><col /><col style={{ width: '180px' }} /><col style={{ width: '130px' }} /><col style={{ width: '130px' }} /><col style={{ width: '130px' }} /><col style={{ width: '210px' }} /><col style={{ width: '88px' }} /></colgroup>
          <TableHeader className="[&_tr]:border-b-0"><TableRow className="hover:bg-transparent">
            <InvoicesTableHead column="name" sortColumn={sortColumn} sortDirection={sortDirection} onToggleSort={onToggleSort} label={labels.invoice} icon={FileText} stickyLeft /><InvoicesTableHead column="status" sortColumn={sortColumn} sortDirection={sortDirection} onToggleSort={onToggleSort} label={labels.status} icon={ListChecks} /><InvoicesTableHead column="decision" sortColumn={sortColumn} sortDirection={sortDirection} onToggleSort={onToggleSort} label={labels.decision} icon={ListChecks} /><InvoicesTableHead column="cost" sortColumn={sortColumn} sortDirection={sortDirection} onToggleSort={onToggleSort} label={labels.totalCost} icon={DollarSign} /><InvoicesTableHead column="duration" sortColumn={sortColumn} sortDirection={sortDirection} onToggleSort={onToggleSort} label={labels.totalTime} icon={Timer} /><InvoicesTableHead column="created" sortColumn={sortColumn} sortDirection={sortDirection} onToggleSort={onToggleSort} label={labels.created} icon={Clock} /><TableHead className="sticky top-0 z-20 border-b bg-muted"><span className="sr-only">{labels.actions}</span></TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {invoicesLoading ? <TableSkeleton columns={7} /> : rows.map(invoice => <TableRow key={invoice.id} className="invoice-table-row" data-openable={invoice.canOpen} onClick={() => { if (invoice.canOpen) void onSelect(invoice.id) }}>
              <TableCell><Tooltip text={invoice.name} onlyWhenTruncated asChild>{invoice.canOpen
                ? <a className="invoice-table-name" href={invoice.href} onClick={onInvoiceLink}>{invoice.name}</a>
                : <span className="invoice-table-name">{invoice.name}</span>}</Tooltip></TableCell>
              <TableCell><Tooltip text={invoice.errorMessage || invoice.statusLabel} asChild><Badge variant="secondary" className="invoice-table-status" data-status={invoice.status}>{invoice.statusIcon === 'spinner' && <LoaderCircle size={13} className="upload-spinner" />}{invoice.statusIcon === 'clock' && <Clock size={13} />}{invoice.statusIcon === 'error' && <CircleAlert size={13} />}{invoice.status === 'error' ? labels.errorStatus : invoice.statusLabel}</Badge></Tooltip></TableCell>
              <TableCell><InvoiceDecisionBadge classification={invoice.payment_decision === null ? null : invoice.payment_decision.classification} label={invoice.decisionLabel} /></TableCell>
              <TableCell><span className="usage-detail tabular-nums">{invoice.costLabel}</span></TableCell>
              <TableCell><span className="usage-detail tabular-nums">{invoice.durationLabel}</span></TableCell>
              <TableCell className="text-muted-foreground">{invoice.dateLabel}</TableCell>
              <TableCell onClick={event => event.stopPropagation()}><div className="invoice-table-action">{invoice.canRedo && <ConfirmButton icon={RotateCcw} variant="redo" label={labels.redo} confirmation={invoice.redoConfirmation} disabled={redoDisabled} onConfirm={() => void onRedo(invoice.id)} />}{invoice.canDelete && <ConfirmButton icon={Trash2} variant="delete" label={labels.delete} confirmation={invoice.deleteConfirmation} disabled={deleting} onConfirm={() => void onDelete(invoice.id)} />}</div></TableCell>
            </TableRow>)}
            {!invoicesLoading && rows.length === 0 && <TableRow className="hover:bg-transparent"><TableCell colSpan={7} className="h-40 text-center text-muted-foreground">{search.trim() ? labels.noResults : labels.emptyList}</TableCell></TableRow>}
          </TableBody>
        </table>
      </div>
    </section>
  )
}
