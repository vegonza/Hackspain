import { Badge } from '@/components/ui/badge'
import { TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import type { useUsage } from '@/hooks/useUsage'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { UsageCostBreakdown } from '@/components/usage/UsageCostBreakdown'

type Props = Pick<ReturnType<typeof useUsage>, 'loading' | 'records' | 'pageKey' | 'labels'>

export function UsageLogTable({ loading, records, pageKey, labels }: Props) {
  return <section className="usage-log">
    <div className="usage-table-scroll" key={pageKey}><table className="usage-table">
      <colgroup><col style={{ width: '21%' }} /><col style={{ width: '13%' }} /><col style={{ width: '22%' }} /><col style={{ width: '12%' }} /><col style={{ width: '20%' }} /><col style={{ width: '12%' }} /></colgroup>
      <TableHeader><TableRow>{[labels.date, labels.provider, labels.model, labels.operation, labels.invoice, labels.cost].map(label => <TableHead key={label}>{label}</TableHead>)}</TableRow></TableHeader>
      <TableBody>{loading ? Array.from({ length: 10 }, (_, row) => <TableRow key={row}>{Array.from({ length: 6 }, (_, cell) => <TableCell key={cell}><Skeleton className="h-4 w-20 max-w-full" /></TableCell>)}</TableRow>)
        : records.map(record => <TableRow key={record.id}>
          <TableCell className="usage-date">{record.date}</TableCell>
          <TableCell><span className="flex items-center gap-2 text-xs"><img src={record.providerLogo} alt="" className="size-5 shrink-0" /><span>{record.providerName}</span></span></TableCell>
          <TableCell><Tooltip text={record.model} onlyWhenTruncated asChild><span className="usage-cell-text usage-model">{record.model}</span></Tooltip></TableCell>
          <TableCell><Badge variant="outline"><span className="size-2 rounded-full" style={{ backgroundColor: record.color }} aria-hidden="true" />{record.operation}</Badge></TableCell>
          <TableCell><Tooltip text={record.invoice_name} onlyWhenTruncated asChild><span className="usage-cell-text">{record.invoice_name}</span></Tooltip></TableCell>
          <TableCell><Tooltip text={<UsageCostBreakdown entries={record.breakdown} total={record.cost} totalLabel={labels.totalCost} />} asChild><span className="usage-detail tabular-nums">{record.cost}</span></Tooltip></TableCell>
        </TableRow>)}
        {!loading && records.length === 0 && <TableRow className="usage-empty-row"><TableCell colSpan={6}>{labels.empty}</TableCell></TableRow>}
      </TableBody>
    </table></div>
  </section>
}
