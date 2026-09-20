import { invoiceFileAccept } from '@/lib/invoiceFiles'
import { ChevronLeft, ChevronRight, Upload, Mail } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SearchInput } from '@/components/ui/search-input'
import { Select } from '@/components/ui/select'
import type { useInvoices } from '@/hooks/useInvoices'
import type { useInvoiceTable } from '@/hooks/useInvoiceTable'

type Props = { table: Omit<ReturnType<typeof useInvoiceTable>, 'mountMonthShortcuts'>; loading: boolean; onGestoria: () => void; onUpload: ReturnType<typeof useInvoices>['onUpload'] }

export function InvoiceBillingHeader({ table, loading, onGestoria, onUpload }: Props) {
  return <header className="billing-header">
    <div className="billing-search-actions">
      <SearchInput className="billing-search" value={table.search} onChange={table.onSearch}
        placeholder={table.labels.search} collapsible={false} />
      <Button asChild size="sm" className="table-add-button"><label className="upload-button">
        <Upload size={15} />{table.labels.upload}
        <input type="file" accept={invoiceFileAccept} multiple onChange={onUpload} aria-label={table.labels.upload} />
      </label></Button>
    </div>
    <Button variant="outline" size="sm" onClick={onGestoria}><Mail size={15} />{table.labels.gestoria}</Button>
    <nav className="billing-month" aria-label={table.labels.period}>
      <Button variant="ghost" size="icon-sm" aria-label={table.labels.previousMonth} aria-keyshortcuts="ArrowLeft" disabled={!table.canNavigateMonths || loading} onClick={table.onPreviousMonth}><ChevronLeft size={16} /></Button>
      <Select value={table.period} onValueChange={table.onPeriod} options={table.monthOptions}
        label={table.labels.period} disabled={loading} showChevron={false} className="billing-month-select" />
      <Button variant="ghost" size="icon-sm" aria-label={table.labels.nextMonth} aria-keyshortcuts="ArrowRight" disabled={!table.canNextMonth || loading} onClick={table.onNextMonth}><ChevronRight size={16} /></Button>
    </nav>
  </header>
}
