import { CalendarClock, CalendarDays, CircleAlert, Euro, FileText } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SortableTableHead } from '@/components/ui/sortable-table-head'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import type { useIncidents } from '@/hooks/useIncidents'

export function IncidentsView({ mount, loading, failed, rows, sortColumn, sortDirection, onToggleSort, onRetry, onInvoiceLink, labels }: ReturnType<typeof useIncidents>) {
  return <section className="incidents-view" ref={mount} aria-label={labels.title} aria-busy={loading}>
    <header className="incidents-header"><div><h1>{labels.title}</h1><p>{labels.subtitle}</p></div></header>
    {failed ? <div role="alert" className="flex items-center gap-3 p-4 text-sm"><span>{labels.failed}</span><Button variant="outline" onClick={onRetry}>{labels.retry}</Button></div>
      : <div className="invoices-table-scroll"><table className="invoices-table incidents-table" aria-busy={loading}>
        <colgroup><col /><col style={{ width: 150 }} /><col style={{ width: 150 }} /><col style={{ width: 150 }} /><col style={{ width: 140 }} /><col style={{ width: 420 }} /></colgroup>
        <TableHeader><TableRow>
          <TableHead className="sticky top-0 left-0 z-30 border-b bg-muted"><span className="incidents-heading"><FileText size={15} />{labels.invoice}</span></TableHead>
          <SortableTableHead column="issued" label={labels.issuedDate} icon={CalendarDays} activeColumn={sortColumn} direction={sortDirection} onToggle={onToggleSort} className="sticky top-0 z-20 border-b bg-muted" />
          <SortableTableHead column="created" label={labels.createdDate} icon={CalendarClock} activeColumn={sortColumn} direction={sortDirection} onToggle={onToggleSort} className="sticky top-0 z-20 border-b bg-muted" />
          <SortableTableHead column="due" label={labels.dueDate} icon={CalendarClock} activeColumn={sortColumn} direction={sortDirection} onToggle={onToggleSort} className="sticky top-0 z-20 border-b bg-muted" />
          <TableHead className="sticky top-0 z-20 border-b bg-muted"><span className="incidents-heading"><Euro size={15} />{labels.amount}</span></TableHead>
          <TableHead className="sticky top-0 z-20 border-b bg-muted"><span className="incidents-heading"><CircleAlert size={15} />{labels.reasons}</span></TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {loading ? <TableSkeleton columns={6} /> : rows.map(incident => <TableRow key={incident.invoice_id} className="invoice-table-row" data-openable="false">
            <TableCell><a className="invoice-table-name" href={incident.href} onClick={onInvoiceLink}>{incident.invoice_name}</a></TableCell>
            <TableCell className="tabular-nums">{incident.issuedLabel}</TableCell>
            <TableCell className="tabular-nums">{incident.createdLabel}</TableCell>
            <TableCell className="tabular-nums">{incident.dueLabel}</TableCell>
            <TableCell className="tabular-nums font-medium">{incident.amountLabel}</TableCell>
            <TableCell><div className="incidents-reasons">{incident.failures.map(failure => <Tooltip key={failure.key} text={failure.reason} asChild><Badge variant="outline">{failure.label}</Badge></Tooltip>)}</div></TableCell>
          </TableRow>)}
          {!loading && rows.length === 0 && <TableRow><TableCell colSpan={6} className="h-40 text-center text-muted-foreground">{labels.empty}</TableCell></TableRow>}
        </TableBody>
      </table></div>}
  </section>
}
