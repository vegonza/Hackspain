import { afterEach, describe, expect, mock, test } from 'bun:test'
import type { MouseEvent } from 'react'
import { documentPath, followLink, navigate, parseRoute } from '../src/hooks/useAppRoute'

const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
const originalPopStateEvent = Object.getOwnPropertyDescriptor(globalThis, 'PopStateEvent')

afterEach(() => {
  if (originalWindow === undefined) Reflect.deleteProperty(globalThis, 'window')
  else Object.defineProperty(globalThis, 'window', originalWindow)
  if (originalPopStateEvent === undefined) Reflect.deleteProperty(globalThis, 'PopStateEvent')
  else Object.defineProperty(globalThis, 'PopStateEvent', originalPopStateEvent)
})

function navigationEnvironment(path: string) {
  const events = new EventTarget()
  const location = { pathname: path }
  const history = {
    pushState: mock((_state: null, _title: string, next: string) => { location.pathname = next }),
    replaceState: mock((_state: null, _title: string, next: string) => { location.pathname = next }),
  }
  Object.defineProperty(globalThis, 'window', { configurable: true, value: Object.assign(events, { location, history }) })
  Object.defineProperty(globalThis, 'PopStateEvent', { configurable: true, value: Event })
  return { events, location, history }
}

describe('document URLs', () => {
  test('document URLs restore the selected document without phase subpaths', () => {
    expect(parseRoute('/docs')).toEqual({ view: 'documents', documentId: null })
    expect(parseRoute('/cost').view).toBe('usage')
    expect(parseRoute(documentPath('invoice-1'))).toEqual({ view: 'documents', documentId: 'invoice-1' })
    for (const section of ['text', 'ocr', 'merge', 'extraction', 'erp']) {
      expect(parseRoute(`/docs/invoice-1/${section}`).view).toBe('not-found')
    }
    expect(documentPath('invoice-1')).toBe('/docs/invoice-1')
    expect(parseRoute('/docs/invoice-1/unknown').view).toBe('not-found')
  })

  test('navigation adds history entries and notifies the route subscriber once per change', () => {
    const { history, location, events } = navigationEnvironment('/docs')
    const onChange = mock(() => {})
    events.addEventListener('popstate', onChange)
    navigate('/docs/invoice-1')
    navigate('/docs/invoice-2')
    navigate('/docs/invoice-2')
    navigate('/cost')
    expect(history.pushState).toHaveBeenCalledTimes(3)
    expect(onChange).toHaveBeenCalledTimes(3)
    location.pathname = '/docs/invoice-2'
    events.dispatchEvent(new Event('popstate'))
    expect(parseRoute(location.pathname).documentId).toBe('invoice-2')
    expect(history.pushState).toHaveBeenCalledTimes(3)
  })

  test('the root URL is replaced instead of adding a redundant Back entry', () => {
    const { history } = navigationEnvironment('/')
    navigate('/docs', true)
    expect(history.replaceState).toHaveBeenCalledWith(null, '', '/docs')
    expect(history.pushState).not.toHaveBeenCalled()
  })

  test('modified clicks retain native link behavior', () => {
    const { history } = navigationEnvironment('/docs')
    for (const modifier of ['ctrlKey', 'metaKey', 'shiftKey', 'altKey']) {
      const preventDefault = mock(() => {})
      followLink({ button: 0, [modifier]: true, preventDefault } as unknown as MouseEvent<HTMLAnchorElement>)
      expect(preventDefault).not.toHaveBeenCalled()
    }
    const preventDefault = mock(() => {})
    followLink({ button: 0, currentTarget: { pathname: '/docs/invoice-1' }, preventDefault } as unknown as MouseEvent<HTMLAnchorElement>)
    expect(preventDefault).toHaveBeenCalledOnce()
    expect(history.pushState).toHaveBeenCalledWith(null, '', '/docs/invoice-1')
  })
})
