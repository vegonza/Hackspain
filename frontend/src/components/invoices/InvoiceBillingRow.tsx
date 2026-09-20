import type { MouseEvent, ReactNode } from 'react'
import { Building2, CircleAlert } from 'lucide-react'
import { InvoiceStatusBadge } from '@/components/invoices/InvoiceStatusBadge'
import { TableCell, TableRow } from '@/components/ui/table'
import { Tooltip } from '@/components/ui/tooltip'
import type { BillingRow } from '@/hooks/invoiceBilling'

type Props = {
  invoice: BillingRow
  actions: ReactNode
  onSelect: (id: string) => void
  onInvoiceLink: (event: MouseEvent<HTMLAnchorElement>) => void
}

export function InvoiceBillingRow({ invoice, actions, onSelect, onInvoiceLink }: Props) {
  return <TableRow className="invoice-table-row billing-row" data-openable={invoice.canOpen} onClick={() => { if (invoice.canOpen) onSelect(invoice.id) }}>
    <TableCell>
      <div className="billing-identity">
        {invoice.logo !== undefined ? <img className="billing-supplier-logo" src={invoice.logo} alt="" width={36} height={36} />
          : <span className="billing-avatar" aria-hidden="true">{invoice.initials === null ? <Building2 size={20} /> : invoice.initials}</span>}
        <div className="billing-identity-text">
          <Tooltip text={invoice.partyName} onlyWhenTruncated asChild>{invoice.canOpen
            ? <a className="invoice-table-name" href={invoice.href} onClick={onInvoiceLink}>{invoice.partyName}</a>
            : <span className="invoice-table-name">{invoice.partyName}</span>}</Tooltip>
          <Tooltip text={invoice.secondary} onlyWhenTruncated asChild><div className="billing-secondary">{invoice.secondary}</div></Tooltip>
        </div>
      </div>
    </TableCell>
    <TableCell>
      <Tooltip text={invoice.badge.description} asChild><span className="billing-status">
        <InvoiceStatusBadge badge={invoice.badge} />
      </span></Tooltip>
    </TableCell>
    <TableCell className="billing-date">{invoice.date}</TableCell>
    <TableCell className="billing-money">
      <strong>{invoice.originalAmount !== null && <Tooltip text={invoice.originalAmount} asChild>
        <span className="billing-currency-info" role="img" aria-label={invoice.originalAmount}><CircleAlert size={13} aria-hidden="true" /></span>
      </Tooltip>}{invoice.amount}</strong>
      <span>{invoice.gross}</span>
    </TableCell>
    <TableCell onClick={event => event.stopPropagation()}><div className="invoice-table-action">{actions}</div></TableCell>
  </TableRow>
}
