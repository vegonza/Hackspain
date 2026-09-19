import { describe, expect, test } from 'bun:test'

import { parseRoute } from '../src/hooks/useAppRoute'

describe('treasury route', () => {
  test('opens the treasury dashboard', () => {
    expect(parseRoute('/treasury')).toEqual({ view: 'treasury', invoiceId: null })
  })

  test('opens the accounting pre-close dashboard', () => {
    expect(parseRoute('/accounting')).toEqual({ view: 'accounting', invoiceId: null })
  })

  test('opens the escalated invoice incidents dashboard', () => {
    expect(parseRoute('/incidents')).toEqual({ view: 'incidents', invoiceId: null })
  })
})
