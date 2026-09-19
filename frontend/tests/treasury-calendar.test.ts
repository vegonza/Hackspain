import { describe, expect, test } from 'bun:test'

import type { TreasuryPayment } from '../src/api/treasury'
import { buildCalendarDays, moveCalendarMonth } from '../src/hooks/treasuryCalendar'

const payments: TreasuryPayment[] = [
  { document_id: 'invoice-1', document_name: 'uno.pdf', supplier_name: 'Alfa', amount: '100.25', due_date: '2026-09-20' },
  { document_id: 'invoice-2', document_name: 'dos.pdf', supplier_name: 'Beta', amount: '50.75', due_date: '2026-09-20' },
  { document_id: 'invoice-3', document_name: 'tres.pdf', supplier_name: 'Gamma', amount: '200.00', due_date: '2026-10-02' },
]

describe('treasury calendar', () => {
  test('groups invoices and amounts on their payment deadline', () => {
    const days = buildCalendarDays('2026-09', payments, '2026-09-20', '2026-09-19')
    const paymentDay = days.find(day => day !== null && day.date === '2026-09-20')
    expect(paymentDay).not.toBeNull()
    expect(paymentDay!.invoiceCount).toBe(2)
    expect(paymentDay!.amount).toBe(151)
    expect(paymentDay!.selected).toBe(true)
  })

  test('keeps payments from other months outside the visible grid', () => {
    const days = buildCalendarDays('2026-09', payments, null, '2026-09-19')
    expect(days.some(day => day !== null && day.date === '2026-10-02')).toBe(false)
    expect(days.length % 7).toBe(0)
  })

  test('navigates across years', () => {
    expect(moveCalendarMonth('2026-12', 1)).toBe('2027-01')
    expect(moveCalendarMonth('2026-01', -1)).toBe('2025-12')
  })
})
