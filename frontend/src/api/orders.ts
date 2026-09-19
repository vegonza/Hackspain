import { fetchJson, fetchEmpty } from '@/api/client'

export interface Order {
  order_id: string
  supplier_id: string
  tax_id: string | null
  amount: string
  status: string
  date: string
}

export function fetchOrders(signal: AbortSignal): Promise<Order[]> {
  return fetchJson('/orders', { signal })
}

export function saveOrder(id: string | null, order: Order): Promise<Order> {
  return fetchJson(id === null ? '/orders' : `/orders/${encodeURIComponent(id)}`, {
    method: id === null ? 'POST' : 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(order),
  })
}

export function deleteOrder(id: string): Promise<void> {
  return fetchEmpty(`/orders/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
