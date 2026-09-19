import { describe, expect, test } from 'bun:test'
import { erpSortValue, filterErpRows, type ErpRow, type ErpSortColumn } from '../src/hooks/erpRows'

function row(overrides: Partial<ErpRow>): ErpRow {
  return {
    id: 'id', href: '/erp/id', entryId: 'AS-00001', orderId: 'PO-2026-0001', supplierId: 'P001', taxId: 'B11111111',
    status: 'PENDIENTE', statusLabel: 'Pendiente', dateLabel: '10/1/2026', dateValue: Date.parse('2026-01-10'),
    amountLabel: '100,00 €', amountValue: 100, warningLabels: [], ...overrides,
  }
}

const rows = [
  row({ id: 'a', entryId: 'AS-00010', orderId: 'PO-2026-0010', supplierId: 'P002', amountValue: 250.5, amountLabel: '250,50 €', dateValue: Date.parse('2026-03-01') }),
  row({ id: 'b', entryId: 'AS-00002', orderId: 'PO-2026-0002', statusLabel: 'Pagada', status: 'PAGADA', amountValue: 99, amountLabel: '99,00 €', dateValue: null, dateLabel: '—' }),
  row({ id: 'c', entryId: 'AS-77001', orderId: 'PO-2026-0538', taxId: '—', amountValue: null, amountLabel: '—', warningLabels: ['Falta el NIF', 'Fecha no válida'] }),
]

const ids = (list: ErpRow[]) => list.map(item => item.id)

describe('ERP table filtering', () => {
  test('an empty search keeps every row', () => {
    expect(ids(filterErpRows(rows, ''))).toEqual(['a', 'b', 'c'])
    expect(ids(filterErpRows(rows, '   '))).toEqual(['a', 'b', 'c'])
  })

  test('the search looks at entry, order, supplier and tax id', () => {
    expect(ids(filterErpRows(rows, 'as-00010'))).toEqual(['a'])
    expect(ids(filterErpRows(rows, '0538'))).toEqual(['c'])
    expect(ids(filterErpRows(rows, 'p002'))).toEqual(['a'])
    expect(ids(filterErpRows(rows, 'b11111111'))).toEqual(['a', 'b'])
  })

  test('the search also matches status, amount and warning texts', () => {
    expect(ids(filterErpRows(rows, 'pagada'))).toEqual(['b'])
    expect(ids(filterErpRows(rows, '250,50'))).toEqual(['a'])
    expect(ids(filterErpRows(rows, 'falta el nif'))).toEqual(['c'])
  })

  test('a search without matches returns nothing', () => {
    expect(filterErpRows(rows, 'no existe')).toEqual([])
  })
})

describe('ERP table sort values', () => {
  const sample = row({
    entryId: 'AS-00010', orderId: 'PO-2026-0010', supplierId: 'P002', taxId: 'B22222222', statusLabel: 'Pagada',
    dateValue: Date.parse('2026-03-01'), amountValue: 250.5, warningLabels: ['Falta el NIF', 'Fecha no válida'],
  })

  test('each column sorts by its own value', () => {
    const expected: Record<ErpSortColumn, string | number | null> = {
      entry: 'AS-00010', order: 'PO-2026-0010', supplier: 'P002', taxId: 'B22222222', status: 'Pagada',
      date: Date.parse('2026-03-01'), amount: 250.5, warnings: 2,
    }
    for (const column of Object.keys(expected) as ErpSortColumn[]) expect(erpSortValue(sample, column)).toBe(expected[column])
  })

  test('dates and amounts sort as numbers, so a missing value can be told apart', () => {
    expect(erpSortValue(rows[1], 'date')).toBeNull()
    expect(erpSortValue(rows[2], 'amount')).toBeNull()
    expect(typeof erpSortValue(rows[0], 'amount')).toBe('number')
  })
})
