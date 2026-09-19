import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { useUsage } from '@/hooks/useUsage'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { UsageCostBreakdown } from '@/components/usage/UsageCostBreakdown'

type Props = Pick<ReturnType<typeof useUsage>, 'loading' | 'records' | 'page' | 'pages' | 'setPage' | 'labels' | 'totalLabel'>

export function UsageLogTable({ loading, records, page, pages, setPage, labels, totalLabel }: Props) {
  return <section className="usage-log">
    <header className="usage-log-header">
      <h2>{labels.history}</h2><span className="usage-record-count">{totalLabel}</span>
      {pages > 1 && <div className="usage-pagination">
        <Button variant="outline" size="icon-sm" disabled={page === 0 || loading} onClick={() => setPage(page - 1)} aria-label={labels.previous}><ChevronLeft size={16} /></Button>
        <span>{page + 1} / {pages}</span>
        <Button variant="outline" size="icon-sm" disabled={page + 1 >= pages || loading} onClick={() => setPage(page + 1)} aria-label={labels.next}><ChevronRight size={16} /></Button>
      </div>}
    </header>
    <div className="usage-table-scroll"><table className="usage-table">
      <colgroup><col style={{ width: '21%' }} /><col style={{ width: '13%' }} /><col style={{ width: '22%' }} /><col style={{ width: '12%' }} /><col style={{ width: '20%' }} /><col style={{ width: '12%' }} /></colgroup>
      <TableHeader><TableRow>{[labels.date, labels.provider, labels.model, labels.operation, labels.document, labels.cost].map(label => <TableHead key={label}>{label}</TableHead>)}</TableRow></TableHeader>
      <TableBody>{loading ? Array.from({ length: 10 }, (_, row) => <TableRow key={row}>{Array.from({ length: 6 }, (_, cell) => <TableCell key={cell}><Skeleton className="h-4 w-20 max-w-full" /></TableCell>)}</TableRow>)
        : records.map(record => <TableRow key={record.id}>
          <TableCell className="usage-date">{record.date}</TableCell>
          <TableCell><span className="flex items-center gap-2 text-xs"><img src={`/providers/${record.provider}.svg`} alt="" className="size-5 shrink-0" /><span>{record.providerName}</span></span></TableCell>
          <TableCell><Tooltip text={record.model} onlyWhenTruncated asChild><span className="usage-cell-text usage-model">{record.model}</span></Tooltip></TableCell>
          <TableCell><Badge variant="outline"><span className="size-2 rounded-full" style={{ backgroundColor: record.color }} aria-hidden="true" />{record.operation}</Badge></TableCell>
          <TableCell><Tooltip text={record.document_name} onlyWhenTruncated asChild><span className="usage-cell-text">{record.document_name}</span></Tooltip></TableCell>
          <TableCell><Tooltip text={<UsageCostBreakdown entries={record.breakdown} total={record.cost} totalLabel={labels.totalCost} />} asChild><span className="usage-detail tabular-nums">{record.cost}</span></Tooltip></TableCell>
        </TableRow>)}
        {!loading && records.length === 0 && <TableRow className="usage-empty-row"><TableCell colSpan={6}>{labels.empty}</TableCell></TableRow>}
      </TableBody>
    </table></div>
  </section>
}
