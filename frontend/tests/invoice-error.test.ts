import { expect, test } from 'bun:test'
import { invoiceErrorKey } from '../src/hooks/invoiceError'

test('spending limits and other denied requests have distinct messages', () => {
  expect(invoiceErrorKey('openrouter_key_limit_exceeded')).toBe('invoices.openrouterKeyLimit')
  expect(invoiceErrorKey('PermissionDeniedError (HTTP 403)')).toBe('invoices.providerAccessDenied')
  expect(invoiceErrorKey('ValueError')).toBe('invoices.error')
  expect(invoiceErrorKey(null)).toBe('invoices.error')
})
