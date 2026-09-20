import { Building2, CalendarClock, Euro, ReceiptText } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import { TreasuryCalendar } from '@/components/treasury/TreasuryCalendar'
import type { useTreasury } from '@/hooks/useTreasury'

export function TreasuryView({ mount, loading, failed, summary, rows, calendar, onRetry, onDocumentLink, labels }: ReturnType<typeof useTreasury>) {
  return <section className="treasury-view" ref={mount} aria-label={labels.title} aria-busy={loading}>
    <div className="treasury-kpis">
      {loading ? Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-32 w-full" />)
        : summary.map(item => <div className="treasury-kpi" key={item.id} data-risk={item.risk}>
          <span>{item.label}</span><strong>{item.value}</strong><small>{item.subtitle}</small>
        </div>)}
    </div>
    {failed ? <div role="alert" className="flex items-center gap-3 p-4 text-sm"><span>{labels.failed}</span><Button variant="outline" onClick={onRetry}>{labels.retry}</Button></div>
      : <><TreasuryCalendar calendar={calendar} labels={labels} loading={loading} onDocumentLink={onDocumentLink} />
      <div className="treasury-table-section">
        <h2>{labels.title}</h2>
        <div className="invoices-table-scroll"><table className="invoices-table" aria-busy={loading}>
          <colgroup><col /><col style={{ width: 220 }} /><col style={{ width: 240 }} /><col style={{ width: 220 }} /></colgroup>
          <TableHeader><TableRow>
            <TableHead><span className="treasury-heading"><Building2 size={15} />{labels.supplier}</span></TableHead>
            <TableHead><span className="treasury-heading"><ReceiptText size={15} />{labels.approvedInvoices}</span></TableHead>
            <TableHead><span className="treasury-heading"><Euro size={15} />{labels.committedAmount}</span></TableHead>
            <TableHead><span className="treasury-heading"><CalendarClock size={15} />{labels.nextDueDate}</span></TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {loading ? <TableSkeleton columns={4} /> : rows.map(row => <TableRow key={row.supplier_name} className="invoice-table-row" data-openable="false">
              <TableCell className="font-medium">{row.supplier_name}</TableCell>
              <TableCell className="tabular-nums">{row.approved_invoices}</TableCell>
              <TableCell className="tabular-nums">{row.displayAmount}</TableCell>
              <TableCell>{row.displayDueDate}</TableCell>
            </TableRow>)}
            {!loading && rows.length === 0 && <TableRow><TableCell colSpan={4} className="h-40 text-center text-muted-foreground">{labels.empty}</TableCell></TableRow>}
          </TableBody>
        </table></div>
      </div></>}
  </section>
}
