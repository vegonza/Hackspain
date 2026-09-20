import { afterEach, beforeEach, describe, expect, mock, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { ApiError } from '../src/api/client'
import { fetchIssuedInvoices, isUnreservedInvoiceError } from '../src/api/issued'
import { useIssuedInvoices } from '../src/hooks/useIssuedInvoices'

const originalFetch = globalThis.fetch
const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
const originalDocument = Object.getOwnPropertyDescriptor(globalThis, 'document')
const originalTimeout = globalThis.setTimeout
const originalClearTimeout = globalThis.clearTimeout
let windowEvents: EventTarget
let documentEvents: EventTarget & { hidden: boolean }
let hook: ReturnType<typeof useIssuedInvoices>
const tick = async () => { for (let index = 0; index < 12; index++) await Promise.resolve() }
const mount = () => hook.mount({} as HTMLElement)!

beforeEach(() => {
  windowEvents = new EventTarget()
  documentEvents = Object.assign(new EventTarget(), { hidden: false })
  Object.defineProperty(globalThis, 'window', { configurable: true, value: windowEvents })
  Object.defineProperty(globalThis, 'document', { configurable: true, value: documentEvents })
  function Harness() { hook = useIssuedInvoices(); return null }
  renderToStaticMarkup(<Harness />)
})
afterEach(() => {
  globalThis.fetch = originalFetch
  globalThis.setTimeout = originalTimeout
  globalThis.clearTimeout = originalClearTimeout
  if (originalWindow === undefined) Reflect.deleteProperty(globalThis, 'window')
  else Object.defineProperty(globalThis, 'window', originalWindow)
  if (originalDocument === undefined) Reflect.deleteProperty(globalThis, 'document')
  else Object.defineProperty(globalThis, 'document', originalDocument)
})

describe('issued invoice refresh', () => {
  test('refreshes on entry, focus, visibility and re-entry, but stops after leaving', async () => {
    const fetch = mock(async () => Response.json([]))
    globalThis.fetch = fetch as unknown as typeof globalThis.fetch
    const leave = mount()
    await tick()
    expect(fetch).toHaveBeenCalledTimes(1)
    windowEvents.dispatchEvent(new Event('focus'))
    await tick()
    expect(fetch).toHaveBeenCalledTimes(2)
    documentEvents.hidden = true
    documentEvents.dispatchEvent(new Event('visibilitychange'))
    await tick()
    expect(fetch).toHaveBeenCalledTimes(2)
    documentEvents.hidden = false
    documentEvents.dispatchEvent(new Event('visibilitychange'))
    await tick()
    expect(fetch).toHaveBeenCalledTimes(3)
    leave()
    windowEvents.dispatchEvent(new Event('focus'))
    documentEvents.dispatchEvent(new Event('visibilitychange'))
    await tick()
    expect(fetch).toHaveBeenCalledTimes(3)
    const leaveAgain = mount()
    await tick()
    expect(fetch).toHaveBeenCalledTimes(4)
    leaveAgain()
  })

  test('deduplicates simultaneous events and aborts an unfinished load on leave', async () => {
    const signals: AbortSignal[] = []
    globalThis.fetch = mock((_url: string, options: RequestInit) => {
      signals.push(options.signal as AbortSignal)
      return new Promise<Response>(() => {})
    }) as unknown as typeof globalThis.fetch
    const leave = mount()
    windowEvents.dispatchEvent(new Event('focus'))
    documentEvents.dispatchEvent(new Event('visibilitychange'))
    expect(signals).toHaveLength(1)
    leave()
    expect(signals[0].aborted).toBe(true)
  })

  test('retries a failed request automatically and cancels pending retries on leave', async () => {
    const scheduled = new Map<number, () => void>()
    let identifier = 0
    globalThis.setTimeout = ((callback: () => void) => { scheduled.set(++identifier, callback); return identifier }) as unknown as typeof setTimeout
    globalThis.clearTimeout = ((id: number) => { scheduled.delete(id) }) as typeof clearTimeout
    const fetch = mock(async () => { throw new TypeError('offline') })
    globalThis.fetch = fetch as unknown as typeof globalThis.fetch
    const leave = mount()
    await tick()
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(scheduled.size).toBe(1)
    scheduled.values().next().value!()
    await tick()
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(scheduled.size).toBe(1)
    leave()
    expect(scheduled.size).toBe(0)
  })
})

describe('issued invoice submission errors', () => {
  test.each([
    [422, [{ loc: ['body', 'items'], type: 'too_long' }]],
    [404, 'billing_client_not_found'],
    [409, 'billing_company_required'],
  ])('allows corrections only after a confirmed pre-reservation rejection: %s', (status, detail) => {
    expect(isUnreservedInvoiceError(new ApiError('rejected', status, detail))).toBe(true)
  })
  test.each([
    new TypeError('offline'), new Error('timeout'),
    new ApiError('failed', 500, 'database_error'),
    new ApiError('rejected', 422, 'verifactu_test_rejected: invalid tax'),
    new ApiError('locked', 409, 'issued_invoice_locked'),
  ])('keeps the same reservation locked for ambiguous or post-reservation failures', error => {
    expect(isUnreservedInvoiceError(error)).toBe(false)
  })
  test('the centralized client preserves the rejection status and detail', async () => {
    globalThis.fetch = mock(async () => Response.json({ detail: 'billing_client_not_found' }, { status: 404 })) as unknown as typeof globalThis.fetch
    try {
      await fetchIssuedInvoices(new AbortController().signal)
      throw new Error('Expected rejection')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect(isUnreservedInvoiceError(error)).toBe(true)
    }
  })
})
