import { describe, expect, test } from 'bun:test'

import { parseRoute } from '../src/hooks/useAppRoute'

describe('treasury route', () => {
  test('opens the treasury dashboard', () => {
    expect(parseRoute('/treasury')).toEqual({ view: 'treasury', documentId: null })
  })
})
