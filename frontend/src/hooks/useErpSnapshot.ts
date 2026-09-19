import { useCallback, useRef, useState, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchErpEntry, fetchErpSnapshot, refreshErpSnapshot, type ErpEntry, type ErpEntryDetail, type ErpSnapshot } from '@/api/erp'
import { documentPath, erpEntryPath, useAppRoute } from '@/hooks/useAppRoute'
import { erpSortValue, filterErpRows, type ErpRow, type ErpSortColumn } from '@/hooks/erpRows'
import { useTableSort } from '@/hooks/useTableSort'

const money = (amount: string | null): string => amount === null ? '—'
  : new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(Number(amount))
const shortDate = (date: string | null): string => date === null ? '—' : new Date(`${date}T00:00:00`).toLocaleDateString('es-ES')
const orDash = (value: string): string => value === '' ? '—' : value

export function useErpSnapshot() {
  const { t } = useTranslation()
  const route = useAppRoute()
  const selectedId = route.view === 'erp' ? route.entryId : null
  const [snapshot, setSnapshot] = useState<ErpSnapshot | null>(null)
  const [detail, setDetail] = useState<ErpEntryDetail | null>(null)
  const [requestedId, setRequestedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [search, setSearch] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const refreshInFlight = useRef(false)
  const snapshotVersion = useRef(0)
  const { sortColumn, sortDirection, onToggleSort, sortRows } = useTableSort<ErpSortColumn>()
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    let active = true
    setLoading(true)
    setFailed(false)
    setRequestedId(selectedId)
    setDetail(null)
    async function load(): Promise<void> {
      try {
        if (selectedId === null) {
          const version = ++snapshotVersion.current
          const result = await fetchErpSnapshot()
          if (active && version === snapshotVersion.current) setSnapshot(result)
        } else {
          const result = await fetchErpEntry(selectedId)
          if (active) setDetail(result)
        }
      } catch {
        if (active) setFailed(true)
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => { active = false }
  }, [selectedId])
  async function onRefresh(): Promise<void> {
    if (refreshInFlight.current) return
    refreshInFlight.current = true
    setRefreshing(true)
    try {
      await refreshErpSnapshot()
      const version = ++snapshotVersion.current
      const result = await fetchErpSnapshot()
      if (version === snapshotVersion.current) {
        setSnapshot(result)
        setFailed(false)
      }
    } catch {
      // The API client displays the error.
    } finally {
      refreshInFlight.current = false
      setRefreshing(false)
    }
  }

  function onEntryLink(event: MouseEvent<HTMLAnchorElement>): void {
    event.stopPropagation()
    route.followLink(event)
  }

  const entries = snapshot === null ? [] : snapshot.entries
  const statusLabel = (status: string): string => status === 'PENDIENTE' || status === 'PAGADA' ? t(`erp.states.${status}`) : status
  const rows: ErpRow[] = entries.map(entry => ({
    id: entry.id,
    href: erpEntryPath(entry.id),
    entryId: entry.entry_id,
    orderId: orDash(entry.order_id),
    supplierId: orDash(entry.supplier_id),
    taxId: orDash(entry.tax_id),
    status: entry.status,
    statusLabel: statusLabel(entry.status),
    dateLabel: shortDate(entry.date),
    dateValue: entry.date === null ? null : Date.parse(entry.date),
    amountLabel: money(entry.amount),
    amountValue: entry.amount === null ? null : Number(entry.amount),
    warningLabels: entry.warnings.map(warning => t(`erp.warnings.${warning}`)),
  }))
  const selected = detail !== null && detail.id === selectedId ? detail : null
  const field = (read: (entry: ErpEntry) => string): string => selected === null ? '—' : read(selected)
  const detailRows = [
    { label: t('erp.status'), value: field(entry => statusLabel(entry.status)) },
    { label: t('erp.expectedAmount'), value: field(entry => money(entry.amount)) },
    { label: t('erp.entry'), value: field(entry => entry.entry_id) },
    { label: t('erp.purchaseOrder'), value: field(entry => orDash(entry.order_id)) },
    { label: t('erp.supplier'), value: field(entry => orDash(entry.supplier_id)) },
    { label: t('erp.nif'), value: field(entry => orDash(entry.tax_id)) },
    { label: t('erp.registeredAt'), value: field(entry => shortDate(entry.date)) },
    { label: t('erp.rawAmount'), value: field(entry => orDash(entry.raw_amount)) },
    { label: t('erp.rawDate'), value: field(entry => orDash(entry.raw_date)) },
    { label: t('erp.warningsLabel'), value: field(entry => entry.warnings.length === 0
      ? t('erp.noWarnings') : entry.warnings.map(warning => t(`erp.warnings.${warning}`)).join('; ')) },
  ]

  return {
    onRefresh, refreshing,
    mount, loading: loading || requestedId !== selectedId, failed, selectedId, onEntryLink, onNavigate: route.followLink,
    rows: sortRows(filterErpRows(rows, search), erpSortValue),
    search, onSearch: setSearch, sortColumn, sortDirection, onToggleSort,
    onSelect: (id: string) => route.navigate(erpEntryPath(id)),
    detailTitle: selected === null ? null : selected.entry_id,
    detailRows,
    linkedDocuments: selected === null ? [] : selected.documents.map(document => ({ id: document.id, name: document.name, href: documentPath(document.id) })),
    summary: snapshot === null ? null : t('erp.entryCount', { count: snapshot.entry_count }),
    labels: {
      refresh: t('erp.refresh'), refreshing: t('erp.refreshing'),
      title: t('erp.snapshotTitle'), search: t('erp.search'), noResults: t('erp.noResults'), emptySnapshot: t('erp.emptySnapshot'),
      entryUnavailable: t('erp.entryUnavailable'), back: t('erp.back'), linkedDocuments: t('erp.linkedDocuments'), noLinkedDocuments: t('erp.noLinkedDocuments'),
      entry: t('erp.entry'), order: t('erp.purchaseOrder'), supplier: t('erp.supplier'), taxId: t('erp.nif'), status: t('erp.status'),
      date: t('erp.registeredAt'), amount: t('erp.expectedAmount'), warnings: t('erp.warningsColumn'),
    },
  }
}
