import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchUsage, retryFailedUsage, type UsageResponse } from '@/api/usage'
import { formatDateLong } from '@/lib/format'

import { useTablePagination } from '@/hooks/useTablePagination'

const money = (amount: string) => `$${new Intl.NumberFormat('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(Number(amount))}`
const detailFields = ['pages_processed', 'prompt_tokens', 'completion_tokens', 'total_tokens'] as const
type UsageOperation = 'extraction' | 'classification'

const operationColors = { extraction: '#7c3aed', classification: '#059669' } satisfies Record<UsageOperation, string>

export function useUsage() {
  const { t } = useTranslation()
  const [data, setData] = useState<UsageResponse | null>(null)
  const loaded = useRef(false)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    setLoading(!loaded.current)
    async function refresh(): Promise<void> {
      try {
        const result = await fetchUsage()
        if (active) { setData(result); loaded.current = true; setFailed(false) }
      } catch {
        if (active) setFailed(true)
      } finally {
        if (active) {
          setLoading(false)
          timer = setTimeout(() => void refresh(), 5000)
        }
      }
    }
    void refresh()
    return () => { active = false; clearTimeout(timer) }
  }, [])
  async function onRetry(): Promise<void> {
    if (retrying) return
    setRetrying(true)
    try {
      await retryFailedUsage()
      setData(await fetchUsage())
    } catch {
      // The API client displays the error.
    } finally {
      setRetrying(false)
    }
  }

  const table = useTablePagination(data === null ? [] : data.records)
  return {
    pagination: table.pagination, pageKey: table.pageKey,
    operations: (Object.keys(operationColors) as UsageOperation[]).map(id => ({ id, label: t(`usage.operations.${id}`), color: operationColors[id] })),
    onRetry, retrying,
    failedPending: data === null ? 0 : data.failed_pending,
    pendingError: t('usage.pendingError', { count: data === null ? 0 : data.failed_pending }),
    mount, loading, failed,
    stats: data === null ? [] : [
      { label: t('usage.totalCost'), value: money(data.summary.cost_usd) },
      { label: t('usage.invoiceCost'), value: money(data.summary.average_invoice_cost_usd) },
      { label: t('usage.pages'), value: String(data.summary.pages) },
    ],
    daily: data === null ? [] : data.daily.map(day => ({ ...day,
      operations: Object.fromEntries(Object.entries(day.operations).map(([operation, cost]) => [operation, Number(cost)])),
      totalLabel: money(day.cost_usd),
      dateLabel: new Date(`${day.date}T00:00:00`).toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' }),
      breakdown: Object.entries(day.operations).filter(([, cost]) => Number(cost) > 0).sort((first, second) => Number(second[1]) - Number(first[1])).map(([operation, cost]) => ({ operation: t(`usage.operations.${operation as UsageOperation}`), cost: money(cost), color: operationColors[operation as UsageOperation] })),
    })),
    records: table.rows.map(record => ({ ...record,
      operation: t(`usage.operations.${record.operation as UsageOperation}`),
      color: operationColors[record.operation as UsageOperation],
      providerName: record.provider,
      providerLogo: `/providers/${record.provider.toLowerCase()}.svg`,
      date: formatDateLong(record.created_at, 'es-ES'),
      cost: money(String(record.usage.reduce((sum, item) => sum + Number(item.cost), 0))),
      breakdown: record.usage.map(item => ({ model: item.model, cost: money(item.cost), details: detailFields.filter(key => key in item.details).map(key => ({ label: t(`usage.breakdown.${key}`), value: String(item.details[key]) })) })),
    })),
    labels: {
      title: t('usage.title'), history: t('usage.history'),
      date: t('usage.date'), invoice: t('usage.invoice'), model: t('usage.model'),
      provider: t('usage.provider'), pages: t('usage.pages'), cost: t('usage.cost'),
      calls: t('usage.calls'),
      operation: t('usage.operation'), totalCost: t('usage.totalCost'),
      empty: t('usage.empty'), failed: t('invoices.requestFailed'), loading: t('invoices.loading'),
      retry: t('invoices.retry'),
    },
  }
}
