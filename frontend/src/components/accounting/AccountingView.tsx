import { AlertTriangle, BookOpenCheck, Download, FileText, ReceiptText, Tags } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import type { useAccounting } from '@/hooks/useAccounting'

export function AccountingView({
  mount, loading, failed, exporting, summary, categories, invoices, periods, years, year,
  onYearChange, onExport, onRetry, onDocumentLink, labels,
}: ReturnType<typeof useAccounting>) {
  return <section className="accounting-view" ref={mount} aria-label={labels.title} aria-busy={loading}>
    <header className="accounting-header">
      <div><h1>{labels.title}</h1><p>{labels.subtitle}</p></div>
      <div className="accounting-controls">
        <select value={year} onChange={onYearChange} aria-label={labels.date}>
          {years.map(value => <option key={value} value={value}>{value}</option>)}
        </select>
        <div className="accounting-periods">
          {periods.map(period => <Button key={period.id} size="sm" variant={period.active ? 'default' : 'outline'} onClick={period.onSelect}>{period.label}</Button>)}
        </div>
        <Button onClick={onExport} disabled={loading || exporting}>
          <Download />{exporting ? labels.exporting : labels.export}
        </Button>
      </div>
    </header>
    <div className="accounting-advisory"><AlertTriangle /><span>{labels.advisory}</span></div>
    {failed ? <div role="alert" className="flex items-center gap-3 p-4 text-sm"><span>{labels.failed}</span><Button variant="outline" onClick={onRetry}>{labels.retry}</Button></div>
      : <>
        <div className="accounting-kpis">
          {loading ? Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-32 w-full" />)
            : summary.map(item => <div className="accounting-kpi" key={item.id} data-risk={item.risk}>
              <span>{item.label}</span><strong>{item.value}</strong><small>{item.subtitle}</small>
            </div>)}
        </div>
        <div className="accounting-section">
          <h2><Tags />{labels.categories}</h2>
          <div className="documents-table-scroll"><table className="documents-table accounting-category-table" aria-busy={loading}>
            <TableHeader><TableRow>
              <TableHead>{labels.category}</TableHead><TableHead>{labels.invoiceCount}</TableHead>
              <TableHead>{labels.taxBase}</TableHead><TableHead>{labels.vat}</TableHead><TableHead>{labels.reviewCount}</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {loading ? <TableSkeleton columns={5} /> : categories.map(category => <TableRow key={category.category} className="document-table-row" data-openable="false">
                <TableCell className="font-medium">{category.label}</TableCell><TableCell>{category.invoice_count}</TableCell>
                <TableCell className="tabular-nums">{category.displayBase}</TableCell><TableCell className="tabular-nums">{category.displayVat}</TableCell>
                <TableCell>{category.review_count}</TableCell>
              </TableRow>)}
              {!loading && categories.length === 0 && <TableRow><TableCell colSpan={5} className="h-28 text-center text-muted-foreground">{labels.empty}</TableCell></TableRow>}
            </TableBody>
          </table></div>
        </div>
        <div className="accounting-section">
          <h2><BookOpenCheck />{labels.invoices}</h2>
          <div className="documents-table-scroll"><table className="documents-table accounting-invoice-table" aria-busy={loading}>
            <colgroup><col /><col /><col /><col /><col /><col /><col /><col /></colgroup>
            <TableHeader><TableRow>
              <TableHead>{labels.invoice}</TableHead><TableHead>{labels.date}</TableHead><TableHead>{labels.supplier}</TableHead>
              <TableHead>{labels.category}</TableHead><TableHead>{labels.account}</TableHead><TableHead>{labels.taxBase}</TableHead>
              <TableHead>{labels.vat}</TableHead><TableHead>{labels.status}</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {loading ? <TableSkeleton columns={8} /> : invoices.map(invoice => <TableRow key={invoice.document_id} className="document-table-row">
                <TableCell><a className="accounting-invoice-link" href={invoice.href} onClick={onDocumentLink} title={labels.openInvoice}><FileText />{invoice.invoice_number === null ? invoice.document_name : invoice.invoice_number}</a></TableCell>
                <TableCell>{invoice.displayDate}</TableCell><TableCell title={invoice.supplier_nif === null ? undefined : invoice.supplier_nif}>{invoice.displaySupplier}</TableCell>
                <TableCell>{invoice.displayCategory}</TableCell><TableCell className="accounting-code">{invoice.account_code}</TableCell>
                <TableCell className="tabular-nums">{invoice.displayBase}</TableCell><TableCell className="tabular-nums">{invoice.displayVat}</TableCell>
                <TableCell><span className="accounting-status" data-status={invoice.status}><ReceiptText />{invoice.displayStatus}</span>{invoice.displayReasons !== '' && <small className="accounting-reasons">{invoice.displayReasons}</small>}</TableCell>
              </TableRow>)}
              {!loading && invoices.length === 0 && <TableRow><TableCell colSpan={8} className="h-40 text-center text-muted-foreground">{labels.empty}</TableCell></TableRow>}
            </TableBody>
          </table></div>
        </div>
      </>}
  </section>
}
