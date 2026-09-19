import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchUsage, retryFailedUsage, type UsageResponse } from '@/api/usage'
import { formatDateLong } from '@/lib/format'


const money = (amount: string) => `$${new Intl.NumberFormat('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(Number(amount))}`
const detailFields = ['pages_processed', 'prompt_tokens', 'completion_tokens', 'total_tokens'] as const
type UsageOperation = 'extraction' | 'classification'

const operationColors = { extraction: '#7c3aed', classification: '#059669' } satisfies Record<UsageOperation, string>

export function useUsage() {
  const { t } = useTranslation()
  const [data, setData] = useState<UsageResponse | null>(null)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const mounted = useRef(false)
  const requestVersion = useRef(0)
  const loadPage = useCallback(async (nextPage: number): Promise<void> => {
    if (!mounted.current) return
    const version = ++requestVersion.current
    setLoading(true)
    setFailed(false)
    try {
      const result = await fetchUsage(nextPage)
      if (mounted.current && version === requestVersion.current) {
        setData(result)
        setPage(nextPage)
      }
    } catch {
      if (mounted.current && version === requestVersion.current) setFailed(true)
    } finally {
      if (mounted.current && version === requestVersion.current) setLoading(false)
    }
  }, [])
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    mounted.current = true
    void loadPage(0)
    return () => { mounted.current = false; ++requestVersion.current }
  }, [loadPage])
  async function onRetry(): Promise<void> {
    if (retrying) return
    setRetrying(true)
    try {
      await retryFailedUsage()
      await loadPage(page)
    } catch {
      // The API client displays the error.
    } finally {
      setRetrying(false)
    }
  }

  const total = data === null ? 0 : data.total
  const pages = data === null ? 1 : Math.max(1, Math.ceil(total / data.page_size))
  const start = data === null || total === 0 ? 0 : page * data.page_size + 1
  const end = data === null ? 0 : Math.min((page + 1) * data.page_size, total)
  return {
    pageKey: String(page),
    pagination: {
      page, pages,
      previousDisabled: loading || page === 0, nextDisabled: loading || page + 1 >= pages,
      onPrevious: () => { if (!loading && page > 0) void loadPage(page - 1) },
      onNext: () => { if (!loading && page + 1 < pages) void loadPage(page + 1) },
      label: t('pagination.label'), previousLabel: t('pagination.previous'), nextLabel: t('pagination.next'),
      rangeLabel: t('pagination.range', { start, end, total }),
      pageLabel: t('pagination.page', { page: page + 1, pages }),
    },
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
    records: (data === null ? [] : data.records).map(record => ({ ...record,
      operation: t(`usage.operations.${record.operation as UsageOperation}`),
      color: operationColors[record.operation as UsageOperation],
      providerName: record.model.split('/')[0],
      providerLogo: `/providers/${record.model.split('/')[0]}.svg`,
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
