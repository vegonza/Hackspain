import type { ReactNode } from 'react'
import { Building2, CalendarDays, Euro, ListChecks } from 'lucide-react'
import { SortableTableHead } from '@/components/ui/sortable-table-head'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { InvoiceBillingSkeleton } from '@/components/invoices/InvoiceBillingSkeleton'
import type { BillingSort } from '@/hooks/invoiceBilling'

type Props = {
  title: string
  tools: ReactNode
  labels: { party: string; status: string; date: string; amount: string; gross: string; actions: string }
  sort: { column: BillingSort | null; direction: 'asc' | 'desc' }
  onSort: (column: BillingSort) => void
  loading: boolean
  empty: boolean
  emptyMessage: string
  error: string | null
  children: ReactNode
}

export function InvoiceBillingSection({ title, tools, labels, sort, onSort, loading, empty, emptyMessage, error, children }: Props) {
  return <section className="billing-section" aria-label={title}>
    <table className="invoices-table billing-table" aria-busy={loading}>
      <colgroup><col /><col className="billing-review-column" /><col style={{ width: '104px' }} /><col style={{ width: '160px' }} /><col style={{ width: '52px' }} /></colgroup>
      <TableHeader className="billing-section-sticky [&_tr]:border-b-0">
        <TableRow className="hover:bg-transparent"><TableHead colSpan={5} className="billing-section-title-cell">
          <div className="billing-section-header"><h2>{title}</h2>{tools}</div>
        </TableHead></TableRow>
        <TableRow className="hover:bg-transparent">
          <SortableTableHead column="supplier" label={labels.party} icon={Building2} activeColumn={sort.column} direction={sort.direction} onToggle={onSort} className="border-b bg-muted" />
          <SortableTableHead column="review" label={labels.status} icon={ListChecks} activeColumn={sort.column} direction={sort.direction} onToggle={onSort} className="border-b bg-muted" />
          <SortableTableHead column="date" label={labels.date} icon={CalendarDays} activeColumn={sort.column} direction={sort.direction} onToggle={onSort} className="border-b bg-muted" />
          <SortableTableHead column="amount" label={labels.amount} icon={Euro} activeColumn={sort.column} direction={sort.direction} onToggle={onSort} className="billing-money-head border-b bg-muted" />
          <TableHead className="border-b bg-muted"><span className="sr-only">{labels.actions}</span></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {loading ? <InvoiceBillingSkeleton actions={labels.actions} gross={labels.gross} /> : error !== null ? <TableRow className="hover:bg-transparent"><TableCell colSpan={5} className="h-48 text-center text-muted-foreground">{error}</TableCell></TableRow>
          : empty ? <TableRow className="hover:bg-transparent"><TableCell colSpan={5} className="h-48 text-center text-muted-foreground">{emptyMessage}</TableCell></TableRow>
          : children}
      </TableBody>
    </table>
  </section>
}
