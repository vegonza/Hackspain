import { useCallback, useRef, useState, type FormEvent } from 'react'
import { useTablePagination } from '@/hooks/useTablePagination'
import { useTableSort } from '@/hooks/useTableSort'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { deleteSupplier, fetchSuppliers, saveSupplier, type Supplier } from '@/api/suppliers'

const emptySupplier: Supplier = { supplier_id: '', legal_name: '', tax_id: '', iban: '', city: '', payment_terms_days: 30 }

export function useSuppliers() {
  const { t } = useTranslation()
  const { sortColumn, sortDirection, onToggleSort, sortRows } = useTableSort<keyof Supplier>()
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const loaded = useRef(false)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [search, setSearch] = useState('')
  const [draft, setDraft] = useState<Supplier>(emptySupplier)
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
    setLoading(!loaded.current)
    setFailed(false)
    void fetchSuppliers(controller.signal).then(rows => {
      if (!controller.signal.aborted) { setSuppliers(rows); loaded.current = true }
    }).catch(() => {
      if (!controller.signal.aborted) setFailed(true)
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [reload])

  function edit(supplier: Supplier | null): void {
    setEditingId(supplier === null ? null : supplier.supplier_id)
    setDraft(supplier === null ? { ...emptySupplier } : { ...supplier })
    setEditing(true)
  }

  function change<K extends keyof Supplier>(field: K, value: Supplier[K]): void {
    setDraft(current => ({ ...current, [field]: value }))
  }

  async function save(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (savingRef.current) return
    savingRef.current = true
    setSaving(true)
    try {
      const result = await saveSupplier(editingId, draft)
      setSuppliers(current => (editingId === null ? [...current, result] : current.map(item => item.supplier_id === editingId ? result : item))
        .sort((a, b) => a.supplier_id.localeCompare(b.supplier_id)))
      setEditing(false)
      toast.success(t('suppliers.saved'))
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
      await deleteSupplier(id)
      setSuppliers(current => current.filter(item => item.supplier_id !== id))
      toast.success(t('suppliers.deleted'))
    } catch {
      // The centralized API client displays request errors.
    } finally {
      deletingRef.current = false
      setDeleting(false)
    }
  }

  const query = search.trim().toLocaleLowerCase('es-ES')
  const table = useTablePagination(sortRows(suppliers.filter(supplier => [supplier.supplier_id, supplier.legal_name, supplier.tax_id, supplier.iban, supplier.city]
      .some(value => value.toLocaleLowerCase('es-ES').includes(query))), (row, column) => row[column]).map(supplier => ({ ...supplier, deleteConfirmation: t('common.deleteConfirmation', { name: supplier.legal_name }) })), JSON.stringify([search, sortColumn, sortDirection]))
  return {
    pagination: table.pagination, pageKey: table.pageKey,
    sortColumn, sortDirection, onToggleSort,
    mount, loading, failed, editing, saving, deleting, onDelete: remove, draft, editingId, search, onSearch: setSearch,
    rows: table.rows,
    onNew: () => edit(null), onEdit: edit, onChange: change, onSave: save,
    onCancel: () => setEditing(false), onRetry: () => setReload(value => value + 1),
    labels: {
      count: t('suppliers.count', { count: suppliers.length }),
      actions: t('common.actions'), delete: t('common.delete'),
      title: t('suppliers.title'), search: t('suppliers.search'), add: t('suppliers.add'), edit: t('suppliers.edit'),
      supplier_id: t('suppliers.id'), legal_name: t('suppliers.name'), tax_id: t('suppliers.taxId'),
      iban: t('suppliers.iban'), city: t('suppliers.city'), payment_terms_days: t('suppliers.terms'),
      days: t('suppliers.days'), save: t('suppliers.save'), saving: t('suppliers.saving'), cancel: t('common.cancel'), close: t('common.close'),
      empty: t('suppliers.empty'), failed: t('invoices.requestFailed'), retry: t('suppliers.retry'),
    },
  }
}
