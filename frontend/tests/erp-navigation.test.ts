import { describe, expect, test } from 'bun:test'
import { erpEntryPath, parseRoute } from '../src/hooks/useAppRoute'

describe('ERP URLs', () => {
  test('the ERP list and each entry have their own URL', () => {
    expect(parseRoute('/erp')).toEqual({ view: 'erp', invoiceId: null, entryId: null })
    expect(parseRoute(erpEntryPath('entry-1'))).toEqual({ view: 'erp', invoiceId: null, entryId: 'entry-1' })
    expect(erpEntryPath('entry-1')).toBe('/erp/entry-1')
  })

  test('deeper or unknown ERP paths are not found', () => {
    expect(parseRoute('/erp/entry-1/extra').view).toBe('not-found')
    expect(parseRoute('/erp/').view).toBe('not-found')
  })

  test('the invoice and cost URLs keep their shape', () => {
    expect(parseRoute('/invoices')).toEqual({ view: 'invoices', invoiceId: null })
    expect(parseRoute('/cost')).toEqual({ view: 'usage', invoiceId: null })
  })
})
