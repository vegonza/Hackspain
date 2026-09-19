import type { TreasuryPayment } from '@/api/treasury'

export interface TreasuryCalendarDay {
  date: string
  dayNumber: number
  invoiceCount: number
  amount: number
  selected: boolean
  today: boolean
}

function twoDigits(value: number): string {
  return value.toString().padStart(2, '0')
}

export function localDateKey(value: Date): string {
  return `${value.getFullYear()}-${twoDigits(value.getMonth() + 1)}-${twoDigits(value.getDate())}`
}

export function currentCalendarMonth(): string {
  return localDateKey(new Date()).slice(0, 7)
}

export function calendarMonthDate(month: string): Date {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Date(year, monthNumber - 1, 1)
}

export function moveCalendarMonth(month: string, distance: number): string {
  const value = calendarMonthDate(month)
  value.setMonth(value.getMonth() + distance)
  return localDateKey(value).slice(0, 7)
}

export function buildCalendarDays(
  month: string,
  payments: TreasuryPayment[],
  selectedDate: string | null,
  today: string,
): Array<TreasuryCalendarDay | null> {
  const monthDate = calendarMonthDate(month)
  const year = monthDate.getFullYear()
  const monthIndex = monthDate.getMonth()
  const leadingDays = (monthDate.getDay() + 6) % 7
  const monthDays = new Date(year, monthIndex + 1, 0).getDate()
  const days: Array<TreasuryCalendarDay | null> = Array.from({ length: leadingDays }, () => null)

  for (let dayNumber = 1; dayNumber <= monthDays; dayNumber += 1) {
    const date = `${year}-${twoDigits(monthIndex + 1)}-${twoDigits(dayNumber)}`
    const dayPayments = payments.filter(payment => payment.due_date === date)
    days.push({
      date,
      dayNumber,
      invoiceCount: dayPayments.length,
      amount: dayPayments.reduce((total, payment) => total + Number(payment.amount), 0),
      selected: selectedDate === date,
      today: today === date,
    })
  }
  while (days.length % 7 !== 0) days.push(null)
  return days
}
