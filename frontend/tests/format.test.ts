import { describe, expect, test } from 'bun:test'
import { formatAmount, formatStatus } from '../src/lib/format'

describe('shared display formatting', () => {
  test('euro amounts use Spanish separators and include the currency', () => {
    expect(formatAmount(12345.67, 'EUR')).toBe('12.345,67\u00a0€')
    expect(formatAmount(-42.5, 'EUR')).toBe('-42,50\u00a0€')
    expect(formatAmount(0, 'EUR')).toBe('0,00\u00a0€')
  })

  test('extracted amounts retain their original currency', () => {
    const dollars = formatAmount(12345.67, 'USD')
    expect(dollars).toContain('12.345,67')
    expect(dollars).toContain('US$')
    expect(dollars).not.toContain('€')
  })

  test('an unspecified currency does not invent a currency symbol', () => {
    expect(formatAmount(12.5, '')).toBe('12,5')
  })

  test('order and ERP states use sentence case without changing their meaning', () => {
    expect(formatStatus('ABIERTO')).toBe('Abierto')
    expect(formatStatus('PENDIENTE')).toBe('Pendiente')
    expect(formatStatus('PAGADA')).toBe('Pagada')
    expect(formatStatus('EN REVISIÓN')).toBe('En revisión')
  })
})
