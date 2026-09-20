import { useCallback, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { createBillingClient, deleteBillingClient, fetchBillingClients, updateBillingClient, type BillingClient, type BillingParty } from '@/api/issued'
import { useTablePagination } from '@/hooks/useTablePagination'
import { useTableSort } from '@/hooks/useTableSort'

const emptyParty: BillingParty = { name: '', tax_id: '', address: '', email: '', logo_url: '' }
type Column = 'name' | 'tax_id' | 'address' | 'email'

export function useClients() {
  const { t } = useTranslation()
  const [clients, setClients] = useState<BillingClient[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [reload, setReload] = useState(0)
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [party, setParty] = useState(emptyParty)
  const [busy, setBusy] = useState(false)
  const saving = useRef(false)
  const [deleting, setDeleting] = useState(false)
  const deletingRef = useRef(false)
  const sort = useTableSort<Column>()
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    const controller = new AbortController()
    setLoading(true); setFailed(false)
    void fetchBillingClients(controller.signal).then(rows => {
      if (!controller.signal.aborted) setClients(rows)
    }).catch(() => { if (!controller.signal.aborted) setFailed(true) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])
  function edit(client: BillingClient | null): void {
    setEditingId(client === null ? null : client.id)
    setParty(client === null ? emptyParty : { ...emptyParty, ...client })
    setEditing(true)
  }
  async function save(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (saving.current) return
    saving.current = true; setBusy(true)
    const value = { name: party.name, tax_id: party.tax_id, address: party.address, email: party.email, logo_url: party.logo_url }
    try {
      const result = editingId === null ? await createBillingClient(value) : await updateBillingClient(editingId, value)
      setClients(current => [...current.filter(client => client.id !== result.id), result].sort((a, b) => a.name.localeCompare(b.name, 'es')))
      setEditing(false); toast.success(t('clients.saved'))
    } catch {
      // API errors are displayed by the centralized client.
    } finally { saving.current = false; setBusy(false) }
  }
  async function remove(id: string): Promise<void> {
    if (deletingRef.current) return
    deletingRef.current = true; setDeleting(true)
    try {
      await deleteBillingClient(id)
      setClients(current => current.filter(client => client.id !== id))
      toast.success(t('clients.deleted'))
    } catch {
      // API errors are displayed by the centralized client.
    } finally { deletingRef.current = false; setDeleting(false) }
  }
  const query = search.trim().toLocaleLowerCase('es')
  const filtered = clients.filter(client => [client.name, client.tax_id, client.address, client.email].some(value => value.toLocaleLowerCase('es').includes(query)))
  const table = useTablePagination(sort.sortRows(filtered, (row, column) => row[column]).map(client => ({ ...client, deleteConfirmation: t('common.deleteConfirmation', { name: client.name }) })), JSON.stringify([search, sort.sortColumn, sort.sortDirection]))
  return {
    ...table, ...sort, mount, reload, loading, failed, editing, saving: busy, deleting, onDelete: remove, draft: party, editingId, search, onSearch: setSearch, onNew: () => edit(null), onEdit: edit,
    onRetry: () => setReload(value => value + 1),
    onCancel: () => { if (!saving.current) setEditing(false) }, onSave: save,
    onChange: (field: keyof BillingParty, value: string) => setParty(current => ({ ...current, [field]: value })),
    labels: { title: t('clients.title'), search: t('clients.search'), add: t('clients.add'), edit: t('clients.edit'), empty: t('clients.empty'), failed: t('invoices.requestFailed'), retry: t('suppliers.retry'),
      name: t('issued.name'), tax_id: t('issued.taxId'), address: t('issued.address'), email: t('issued.email'), logo_url: t('issued.logo'), actions: t('common.actions'), delete: t('common.delete'),
      close: t('common.close'), cancel: t('common.cancel'), save: t('suppliers.save'), saving: t('suppliers.saving') },
  }
}
