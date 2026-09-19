import { ArrowRight, CalendarDays, ChevronLeft, ChevronRight, FileText } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { useTreasury } from '@/hooks/useTreasury'

type TreasuryState = ReturnType<typeof useTreasury>

interface Props {
  calendar: TreasuryState['calendar']
  labels: TreasuryState['labels']
  loading: boolean
  onDocumentLink: TreasuryState['onDocumentLink']
}

export function TreasuryCalendar({ calendar, labels, loading, onDocumentLink }: Props) {
  return <section className="treasury-calendar-section" aria-label={labels.calendarTitle}>
    <header className="treasury-calendar-header">
      <div><span className="treasury-heading"><CalendarDays size={16} />{labels.calendarTitle}</span><small>{labels.paymentLimit}</small></div>
      <div className="treasury-calendar-navigation">
        <Button variant="ghost" size="icon-sm" onClick={calendar.onPreviousMonth} title={labels.previousMonth}><ChevronLeft /></Button>
        <strong>{calendar.month}</strong>
        <Button variant="ghost" size="icon-sm" onClick={calendar.onNextMonth} title={labels.nextMonth}><ChevronRight /></Button>
      </div>
    </header>
    {loading ? <div className="treasury-calendar-skeleton"><Skeleton className="h-96 w-full" /><Skeleton className="h-96 w-full" /></div>
      : <div className="treasury-calendar-layout">
        <div className="treasury-calendar">
          <div className="treasury-calendar-weekdays">{labels.weekdays.map(day => <span key={day}>{day}</span>)}</div>
          <div className="treasury-calendar-grid">{calendar.days.map((day, index) => day === null
            ? <span className="treasury-calendar-empty-day" key={`empty-${index}`} />
            : <button type="button" className="treasury-calendar-day" key={day.date} disabled={day.invoiceCount === 0}
              data-selected={day.selected} data-today={day.today} data-has-payments={day.invoiceCount > 0}
              onClick={() => calendar.onSelectDate(day.date)} aria-label={day.ariaLabel} aria-pressed={day.selected}>
              <span className="treasury-calendar-day-number">{day.dayNumber}</span>
              {day.invoiceCount > 0 && <><span className="treasury-calendar-marker" />
                <strong>{day.displayAmount}</strong><small>{day.invoiceCount}×</small></>}
            </button>)}</div>
          {!calendar.hasPayments && <p className="treasury-calendar-empty">{labels.noPaymentsThisMonth}</p>}
        </div>
        <aside className="treasury-calendar-details" aria-live="polite">
          {calendar.selectedDate === null ? <div className="treasury-calendar-prompt"><CalendarDays /><p>{labels.selectPaymentDate}</p></div>
            : <><h3>{labels.selectedDateTitle(calendar.selectedDate)}</h3>
              <div className="treasury-calendar-invoices">{calendar.selectedPayments.map(payment => <a className="treasury-calendar-invoice"
                href={payment.href} onClick={onDocumentLink} key={payment.document_id}>
                <FileText /><span><strong>{payment.document_name}</strong><small>{payment.supplier_name}</small></span>
                <span className="treasury-calendar-invoice-amount"><strong>{payment.displayAmount}</strong><small>{labels.openInvoice}</small></span><ArrowRight />
              </a>)}</div></>}
        </aside>
      </div>}
  </section>
}
