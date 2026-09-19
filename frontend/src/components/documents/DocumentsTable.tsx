import { StageMetricsTooltip } from '@/components/documents/StageMetricsTooltip'
import { DocumentsTableHead } from '@/components/documents/DocumentsTableHead'
import { Badge } from '@/components/ui/badge'
import { CircleAlert, Timer, DollarSign, Clock, FileText, ListChecks, LoaderCircle, Upload } from 'lucide-react'
import type { useDocuments } from '@/hooks/useDocuments'
import { SearchInput } from '@/components/ui/search-input'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip } from '@/components/ui/tooltip'
import { DeleteButton } from '@/components/ui/delete-button'

type Props = Pick<ReturnType<typeof useDocuments>, 'onUpload' | 'search' | 'onSearch' | 'onSelect' | 'onDelete' | 'deleting' | 'labels'> & {
  rows: ReturnType<typeof useDocuments>['filteredDocuments']
}

export function DocumentsTable({ onUpload, rows, search, onSearch, onSelect, onDelete, deleting, labels }: Props) {
  return (
    <section className="documents-browser" aria-label={labels.library}>
      <header className="documents-toolbar">
        <SearchInput value={search} onChange={onSearch} placeholder={labels.search} collapsible={false} />
        <label className="upload-button">
          <Upload size={15} />{labels.upload}
          <input type="file" accept="application/pdf,.pdf" multiple onChange={onUpload} aria-label={labels.upload} />
        </label>
      </header>
      <div className="documents-table-scroll">
        <table className="documents-table">
          <colgroup><col /><col style={{ width: '180px' }} /><col style={{ width: '130px' }} /><col style={{ width: '130px' }} /><col style={{ width: '210px' }} /><col style={{ width: '48px' }} /></colgroup>
          <TableHeader className="[&_tr]:border-b-0"><TableRow className="hover:bg-transparent">
            <DocumentsTableHead label={labels.document} icon={FileText} stickyLeft /><DocumentsTableHead label={labels.status} icon={ListChecks} /><DocumentsTableHead label={labels.totalCost} icon={DollarSign} /><DocumentsTableHead label={labels.totalTime} icon={Timer} /><DocumentsTableHead label={labels.created} icon={Clock} /><TableHead className="sticky top-0 z-20 border-b bg-muted"><span className="sr-only">{labels.delete}</span></TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {rows.map(document => <TableRow key={document.id} className="document-table-row" data-openable={document.canOpen} onClick={() => { if (document.canOpen) void onSelect(document.id) }}>
              <TableCell><Tooltip text={document.name} onlyWhenTruncated asChild><button className="document-table-name" disabled={!document.canOpen} onClick={event => { event.stopPropagation(); void onSelect(document.id) }}>{document.name}</button></Tooltip></TableCell>
              <TableCell><Tooltip text={document.errorMessage || document.statusLabel} asChild><Badge variant="secondary" className="document-table-status" data-status={document.status}>{document.statusIcon === 'spinner' && <LoaderCircle size={13} className="upload-spinner" />}{document.statusIcon === 'clock' && <Clock size={13} />}{document.statusIcon === 'error' && <CircleAlert size={13} />}{document.status === 'error' ? labels.errorStatus : document.statusLabel}</Badge></Tooltip></TableCell>
              <TableCell><Tooltip text={<StageMetricsTooltip rows={document.costBreakdown} total={document.costLabel} title={labels.totalCost} />} asChild><span className="usage-detail tabular-nums">{document.costLabel}</span></Tooltip></TableCell>
              <TableCell><Tooltip text={<StageMetricsTooltip rows={document.durationBreakdown} total={document.durationLabel} title={labels.totalTime} />} asChild><span className="usage-detail tabular-nums">{document.durationLabel}</span></Tooltip></TableCell>
              <TableCell className="text-muted-foreground">{document.dateLabel}</TableCell>
              <TableCell onClick={event => event.stopPropagation()}>{document.canDelete && <DeleteButton label={labels.delete} confirmation={document.deleteConfirmation} disabled={deleting} onDelete={() => void onDelete(document.id)} />}</TableCell>
            </TableRow>)}
            {rows.length === 0 && <TableRow className="hover:bg-transparent"><TableCell colSpan={6} className="h-40 text-center text-muted-foreground">{search.trim() ? labels.noResults : labels.emptyList}</TableCell></TableRow>}
          </TableBody>
        </table>
      </div>
    </section>
  )
}
