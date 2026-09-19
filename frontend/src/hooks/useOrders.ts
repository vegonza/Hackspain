import { useCallback, useRef, useState, type FormEvent } from 'react'
import { useTableSort } from '@/hooks/useTableSort'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { deleteOrder, fetchOrders, saveOrder, type Order } from '@/api/orders'

const emptyOrder: Order = { order_id: '', supplier_id: '', tax_id: null, amount: '', status: 'ABIERTO', date: '' }
const amountFormat = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const dateFormat = new Intl.DateTimeFormat('es-ES')

export function useOrders() {
  const { t } = useTranslation()
  const { sortColumn, sortDirection, onToggleSort, sortRows } = useTableSort<keyof Order>()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [search, setSearch] = useState('')
  const [draft, setDraft] = useState<Order>(emptyOrder)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const savingRef = useRef(false)
  const [deleting, setDeleting] = useState(false)
  const deletingRef = useRef(false)
  const [reload, setReload] = useState(0)
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    const controller = new AbortController()
    setLoading(true)
    setFailed(false)
    void fetchOrders(controller.signal).then(rows => {
      if (!controller.signal.aborted) setOrders(rows)
    }).catch(() => {
      if (!controller.signal.aborted) setFailed(true)
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [reload])

  function edit(order: Order | null): void {
    setEditingId(order === null ? null : order.order_id)
    setDraft(order === null ? { ...emptyOrder } : { ...order })
    setEditing(true)
  }

  function change<K extends keyof Order>(field: K, value: Order[K]): void {
    setDraft(current => ({ ...current, [field]: value }))
  }

  async function save(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (savingRef.current) return
    savingRef.current = true
    setSaving(true)
    try {
      const result = await saveOrder(editingId, draft)
      setOrders(current => (editingId === null ? [...current, result] : current.map(item => item.order_id === editingId ? result : item))
        .sort((a, b) => a.order_id.localeCompare(b.order_id)))
      setEditing(false)
      toast.success(t('orders.saved'))
    } catch {
      // The centralized API client displays request errors.
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  async function remove(id: string): Promise<void> {
    if (deletingRef.current) return
    deletingRef.current = true
    setDeleting(true)
    try {
      await deleteOrder(id)
      setOrders(current => current.filter(item => item.order_id !== id))
      toast.success(t('orders.deleted'))
    } catch {
      // The centralized API client displays request errors.
    } finally {
      deletingRef.current = false
      setDeleting(false)
    }
  }

  const query = search.trim().toLocaleLowerCase('es-ES')
  return {
    sortColumn, sortDirection, onToggleSort,
    mount, loading, failed, editing, saving, deleting, onDelete: remove, draft, editingId, search, onSearch: setSearch,
    rows: sortRows(orders.filter(order => [order.order_id, order.supplier_id, order.tax_id ?? '', order.amount, order.status, order.date]
      .some(value => value.toLocaleLowerCase('es-ES').includes(query))),
      (row, column) => column === 'amount' ? Number(row.amount) : row[column])
      .map(order => ({
        ...order,
        displayAmount: amountFormat.format(Number(order.amount)),
        displayDate: dateFormat.format(new Date(`${order.date}T00:00:00`)),
      })),
    onNew: () => edit(null), onEdit: edit, onChange: change, onSave: save,
    onCancel: () => setEditing(false), onRetry: () => setReload(value => value + 1),
    labels: {
      count: t('orders.count', { count: orders.length }),
      actions: t('common.actions'), delete: t('common.delete'), holdDelete: t('common.holdDelete'),
      title: t('orders.title'), search: t('orders.search'), add: t('orders.add'), edit: t('orders.edit'),
      order_id: t('orders.id'), supplier_id: t('orders.supplier'), tax_id: t('orders.taxId'),
      amount: t('orders.amount'), status: t('orders.status'), date: t('orders.date'),
      save: t('orders.save'), saving: t('orders.saving'), cancel: t('common.cancel'), close: t('common.close'),
      empty: t('orders.empty'), failed: t('invoices.requestFailed'), retry: t('orders.retry'),
    },
  }
}
