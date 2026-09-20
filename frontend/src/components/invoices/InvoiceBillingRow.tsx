import { Building2, CircleAlert, Clock, LoaderCircle } from 'lucide-react'
import { InvoiceActionsMenu } from '@/components/invoices/InvoiceActionsMenu'
import { InvoiceDecisionBadge } from '@/components/invoices/InvoiceDecisionBadge'
import { Badge } from '@/components/ui/badge'
import { TableCell, TableRow } from '@/components/ui/table'
import { Tooltip } from '@/components/ui/tooltip'
import type { InvoicesTableProps } from '@/components/invoices/InvoicesTable'
import type { useInvoiceTable } from '@/hooks/useInvoiceTable'

type Props = Pick<InvoicesTableProps, 'onSelect' | 'onInvoiceLink' | 'onRedo' | 'onDelete' | 'deleting' | 'redoDisabled'> & {
  invoice: ReturnType<typeof useInvoiceTable>['rows'][number]
  labels: ReturnType<typeof useInvoiceTable>['labels']
  downloading: string | null
  onDownload: (id: string) => void
}

export function InvoiceBillingRow({ invoice, labels, downloading, onDownload, onSelect, onInvoiceLink, onRedo, onDelete, deleting, redoDisabled }: Props) {
  return <TableRow className="invoice-table-row billing-row" data-openable={invoice.canOpen} onClick={() => { if (invoice.canOpen) onSelect(invoice.id) }}>
    <TableCell>
      <div className="billing-identity">
        {invoice.logo !== undefined ? <img className="billing-supplier-logo" src={invoice.logo} alt="" width={36} height={36} />
          : <span className="billing-avatar" aria-hidden="true">{invoice.initials === null ? <Building2 size={20} /> : invoice.initials}</span>}
        <div className="billing-identity-text">
          <Tooltip text={invoice.supplier} onlyWhenTruncated asChild>{invoice.canOpen
            ? <a className="invoice-table-name" href={invoice.href} onClick={onInvoiceLink}>{invoice.supplier}</a>
            : <span className="invoice-table-name">{invoice.supplier}</span>}</Tooltip>
          <Tooltip text={invoice.secondary} onlyWhenTruncated asChild><div className="billing-secondary">
            {invoice.secondary}
          </div></Tooltip>
        </div>
      </div>
    </TableCell>
    <TableCell>
      <Tooltip text={invoice.decisionDescription} asChild><span className="billing-status">{invoice.showStatus ? <Badge variant="secondary" className="invoice-table-status" data-status={invoice.status}>
        {invoice.status === 'processing' || invoice.status === 'uploading' ? <LoaderCircle size={13} className="animate-spin" />
          : invoice.status === 'error' ? <CircleAlert size={13} /> : <Clock size={13} />}{invoice.statusLabel}
      </Badge> : <InvoiceDecisionBadge classification={invoice.classification} label={invoice.decisionLabel} />}</span></Tooltip>
    </TableCell>
    <TableCell className="billing-date">{invoice.date}</TableCell>
    <TableCell className="billing-money">
      <strong>{invoice.originalAmount !== null && <Tooltip text={invoice.originalAmount} asChild>
        <span className="billing-currency-info" role="img" aria-label={invoice.originalAmount}><CircleAlert size={13} aria-hidden="true" /></span>
      </Tooltip>}{invoice.amount}</strong>
      <span>{invoice.gross}</span>
    </TableCell>
    <TableCell onClick={event => event.stopPropagation()}>
      <div className="invoice-table-action">
        <InvoiceActionsMenu labels={labels} redoConfirmation={invoice.redoConfirmation} deleteConfirmation={invoice.deleteConfirmation}
          redoDisabled={redoDisabled || !invoice.canManage} deleteDisabled={deleting || !invoice.canManage}
          downloadDisabled={!invoice.canOpen || downloading !== null} downloading={downloading === invoice.id}
          onRedo={() => void onRedo(invoice.id)} onDelete={() => void onDelete(invoice.id)} onDownload={() => onDownload(invoice.id)} />
      </div>
    </TableCell>
  </TableRow>
}
