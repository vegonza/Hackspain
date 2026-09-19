import { useSyncExternalStore, type MouseEvent } from 'react'

export type AppRoute =
  | { view: 'invoices'; invoiceId: string | null }
  | { view: 'usage' | 'orders' | 'suppliers' | 'not-found'; invoiceId: null }
  | { view: 'erp'; invoiceId: null; entryId: string | null }

export function parseRoute(path: string): AppRoute {
  if (path === '/' || path === '/invoices') return { view: 'invoices', invoiceId: null }
  if (path === '/orders') return { view: 'orders', invoiceId: null }
  if (path === '/suppliers') return { view: 'suppliers', invoiceId: null }
  if (path === '/cost') return { view: 'usage', invoiceId: null }
  if (path === '/erp') return { view: 'erp', invoiceId: null, entryId: null }
  const entry = /^\/erp\/([^/]+)$/.exec(path)
  if (entry !== null) return { view: 'erp', invoiceId: null, entryId: entry[1] }
  const match = /^\/invoices\/([^/]+)$/.exec(path)
  if (match !== null) return { view: 'invoices', invoiceId: match[1] }
  return { view: 'not-found', invoiceId: null }
}

export function invoicePath(id: string): string {
  return `/invoices/${id}`
}

export function erpEntryPath(id: string): string {
  return `/erp/${id}`
}

function subscribe(listener: () => void): () => void {
  window.addEventListener('popstate', listener)
  return () => window.removeEventListener('popstate', listener)
}

function pathname(): string {
  return window.location.pathname
}

export function navigate(path: string, replace = false): void {
  if (path === window.location.pathname) return
  if (replace) window.history.replaceState(null, '', path)
  else window.history.pushState(null, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function followLink(event: MouseEvent<HTMLAnchorElement>): void {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  navigate(event.currentTarget.pathname)
}

export function useAppRoute() {
  const path = useSyncExternalStore(subscribe, pathname)
  return { ...parseRoute(path), navigate, followLink }
}
