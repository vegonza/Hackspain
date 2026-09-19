import {
  AlertTriangle, BadgeEuro, BookOpenCheck, CalendarRange, CircleAlert, CircleCheck,
  Download, FileText, ReceiptText, Sparkles, Tags, WalletCards,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TableSkeleton } from '@/components/ui/table/table-skeleton'
import type { useAccounting } from '@/hooks/useAccounting'

export function AccountingView({
  mount, loading, failed, exporting, summary, categories, invoices, periods, years, year, readiness, selectedPeriod,
  onYearChange, onExport, onRetry, onDocumentLink, labels,
}: ReturnType<typeof useAccounting>) {
  return <section className="accounting-view" ref={mount} aria-label={labels.title} aria-busy={loading}>
    <header className="accounting-hero">
      <div className="accounting-hero-copy">
        <span className="accounting-eyebrow"><Sparkles />{labels.controlCenter}</span>
        <h1>{labels.title}</h1>
        <p>{labels.subtitle}</p>
      </div>
      <div className="accounting-toolbar">
        <div className="accounting-period-label"><CalendarRange /><span>{labels.period}</span><strong>{selectedPeriod}</strong></div>
        <div className="accounting-controls">
          <select value={year} onChange={onYearChange} aria-label={labels.date}>
            {years.map(value => <option key={value} value={value}>{value}</option>)}
          </select>
          <div className="accounting-periods">
            {periods.map(period => <Button key={period.id} size="sm" variant={period.active ? 'default' : 'outline'} onClick={period.onSelect}>{period.label}</Button>)}
          </div>
          <Button className="accounting-export" onClick={onExport} disabled={loading || exporting}>
            <Download />{exporting ? labels.exporting : labels.export}
          </Button>
        </div>
      </div>
    </header>

    {failed ? <div role="alert" className="accounting-error"><CircleAlert /><span>{labels.failed}</span><Button variant="outline" onClick={onRetry}>{labels.retry}</Button></div>
      : <main className="accounting-content">
        <div className="accounting-kpis">
          {loading ? Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-36 w-full rounded-2xl" />)
            : summary.map(item => <article className="accounting-kpi" key={item.id} data-tone={item.tone}>
              <div className="accounting-kpi-top">
                <span>{item.label}</span>
                <span className="accounting-kpi-icon" aria-hidden="true">
                  {item.id === 'recorded' && <WalletCards />}
                  {item.id === 'deductible-expenses' && <CircleCheck />}
                  {item.id === 'deductible-vat' && <BadgeEuro />}
                  {item.id === 'review' && <CircleAlert />}
                </span>
              </div>
              <strong>{item.value}</strong>
              <small>{item.subtitle}</small>
            </article>)}
        </div>

        <div className="accounting-overview">
          <section className="accounting-readiness-card">
            <header className="accounting-card-heading">
              <div className="accounting-heading-icon"><BookOpenCheck /></div>
              <div><h2>{labels.readiness}</h2><p>{labels.overview}</p></div>
            </header>
            {loading || readiness === null ? <Skeleton className="h-64 w-full rounded-xl" />
              : <div className="accounting-readiness-body">
                <div className="accounting-progress-ring" style={readiness.progressStyle} aria-label={readiness.displayRate}>
                  <div><strong>{readiness.rate}%</strong><span>{labels.ready}</span></div>
                </div>
                <p>{readiness.description}</p>
                <div className="accounting-readiness-stats">
                  <div data-status="PREPARED"><span><CircleCheck />{labels.ready}</span><strong>{readiness.prepared}</strong></div>
                  <div data-status="REVIEW"><span><CircleAlert />{labels.pending}</span><strong>{readiness.review}</strong></div>
                </div>
              </div>}
          </section>

          <section className="accounting-categories-card">
            <header className="accounting-card-heading accounting-card-heading-wide">
              <div className="accounting-heading-icon"><Tags /></div>
              <div><h2>{labels.categories}</h2><p>{labels.categoriesSubtitle}</p></div>
            </header>
            {loading ? <div className="accounting-category-skeletons">{Array.from({ length: 5 }, (_, index) => <Skeleton key={index} className="h-16 w-full" />)}</div>
              : categories.length === 0 ? <div className="accounting-empty">{labels.empty}</div>
                : <div className="accounting-category-list">
                  {categories.map(category => <article className="accounting-category" key={category.category} data-category={category.category}>
                    <div className="accounting-category-title"><div><span className="accounting-category-dot" />
                      <strong>{category.label}</strong></div><strong>{category.displayBase}</strong></div>
                    <div className="accounting-category-track"><span style={category.barStyle} /></div>
                    <div className="accounting-category-meta">
                      <span>{category.displayShare}</span><span>{category.displayInvoices}</span>
                      <span>{labels.vatShort} {category.displayVat}</span>
                      {category.review_count > 0 && <span data-warning="true">{category.displayReview}</span>}
                    </div>
                  </article>)}
                </div>}
          </section>
        </div>

        <div className="accounting-advisory"><AlertTriangle /><span>{labels.advisory}</span></div>

        <section className="accounting-section">
          <header className="accounting-section-heading">
            <div className="accounting-heading-icon"><ReceiptText /></div>
            <div><h2>{labels.invoices}</h2><p>{labels.invoicesSubtitle}</p></div>
            <span className="accounting-invoice-count">{labels.invoiceTotal}</span>
          </header>
          <div className="documents-table-scroll"><table className="documents-table accounting-invoice-table" aria-busy={loading}>
            <colgroup><col /><col /><col /><col /><col /><col /><col /><col /></colgroup>
            <TableHeader><TableRow>
              <TableHead>{labels.invoice}</TableHead><TableHead>{labels.date}</TableHead><TableHead>{labels.supplier}</TableHead>
              <TableHead>{labels.category}</TableHead><TableHead>{labels.account}</TableHead><TableHead>{labels.taxBase}</TableHead>
              <TableHead>{labels.vat}</TableHead><TableHead>{labels.status}</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {loading ? <TableSkeleton columns={8} /> : invoices.map(invoice => <TableRow key={invoice.document_id} className="document-table-row" data-status={invoice.status}>
                <TableCell><a className="accounting-invoice-link" href={invoice.href} onClick={onDocumentLink} title={labels.openInvoice}><FileText />{invoice.invoice_number === null ? invoice.document_name : invoice.invoice_number}</a></TableCell>
                <TableCell className="accounting-date">{invoice.displayDate}</TableCell><TableCell title={invoice.supplier_nif === null ? undefined : invoice.supplier_nif}>{invoice.displaySupplier}</TableCell>
                <TableCell>{invoice.displayCategory}</TableCell><TableCell><span className="accounting-code">{invoice.account_code}</span></TableCell>
                <TableCell className="tabular-nums accounting-amount">{invoice.displayBase}</TableCell><TableCell className="tabular-nums accounting-amount">{invoice.displayVat}</TableCell>
                <TableCell><span className="accounting-status" data-status={invoice.status}>{invoice.status === 'PREPARED' ? <CircleCheck /> : <CircleAlert />}{invoice.displayStatus}</span>{invoice.displayReasons !== '' && <small className="accounting-reasons">{invoice.displayReasons}</small>}</TableCell>
              </TableRow>)}
              {!loading && invoices.length === 0 && <TableRow><TableCell colSpan={8} className="h-40 text-center text-muted-foreground">{labels.empty}</TableCell></TableRow>}
            </TableBody>
          </table></div>
        </section>
      </main>}
  </section>
}
