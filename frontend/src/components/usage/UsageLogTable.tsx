import { Building2, Clock, Cpu, DollarSign, FileText, Workflow } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import type { useUsage } from '@/hooks/useUsage'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { UsageCostBreakdown } from '@/components/usage/UsageCostBreakdown'

type Props = Pick<ReturnType<typeof useUsage>, 'loading' | 'records' | 'pageKey' | 'labels'>

export function UsageLogTable({ loading, records, pageKey, labels }: Props) {
  const columns = [
    { label: labels.date, icon: Clock },
    { label: labels.provider, icon: Building2 },
    { label: labels.model, icon: Cpu },
    { label: labels.operation, icon: Workflow },
    { label: labels.invoice, icon: FileText },
    { label: labels.cost, icon: DollarSign },
  ]
  return <section className="usage-log">
    <div className="usage-table-scroll" key={pageKey}><table className="usage-table" aria-busy={loading}>
      <colgroup><col style={{ width: '21%' }} /><col style={{ width: '13%' }} /><col style={{ width: '22%' }} /><col style={{ width: '12%' }} /><col style={{ width: '20%' }} /><col style={{ width: '12%' }} /></colgroup>
      <TableHeader><TableRow className="hover:bg-transparent">{columns.map(({ label, icon: Icon }) => <TableHead key={label} className="h-12">
        <span className="flex items-center gap-1"><Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />{label}</span>
      </TableHead>)}</TableRow></TableHeader>
      <TableBody>{loading ? <TableSkeleton columns={6} />
        : records.map(record => <TableRow key={record.id} className="invoice-table-row" data-openable="false">
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
