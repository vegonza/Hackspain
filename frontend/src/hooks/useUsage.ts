import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchUsage, retryFailedUsage, type UsageResponse } from '@/api/usage'
import { formatDateLong } from '@/lib/format'
import type { StageId } from '@/api/invoices'

const money = (amount: string) => `$${new Intl.NumberFormat('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(Number(amount))}`
const detailFields = ['pages_processed', 'prompt_tokens', 'completion_tokens', 'total_tokens'] as const
type UsageOperation = StageId | 'merge' | 'classification'

const phaseColors = { text: '#64748b', ocr: '#2563eb', merge: '#d97706', extraction: '#7c3aed', classification: '#059669' } satisfies Record<UsageOperation, string>

export function useUsage() {
  const { t } = useTranslation()
  const [data, setData] = useState<UsageResponse | null>(null)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const mount = useCallback((node: HTMLElement | null) => {
    if (node === null) return
    let active = true
    let timer: ReturnType<typeof setTimeout>
    setLoading(true)
    async function refresh(): Promise<void> {
      try {
        const result = await fetchUsage(page)
        if (active) { setData(result); setFailed(false) }
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
  }, [page])
  async function onRetry(): Promise<void> {
    if (retrying) return
    setRetrying(true)
    try {
      await retryFailedUsage()
      setData(await fetchUsage(page))
    } catch {
      // The API client displays the error.
    } finally {
      setRetrying(false)
    }
  }

  return {
    phases: (Object.keys(phaseColors) as UsageOperation[]).map(id => ({ id, label: t(id === 'merge' ? 'usage.historicalMerge' : `pipeline.stages.${id}`), color: phaseColors[id] })),
    onRetry, retrying,
    failedPending: data === null ? 0 : data.failed_pending,
    pendingError: t('usage.pendingError', { count: data === null ? 0 : data.failed_pending }),
    mount, loading, failed, page, setPage,
    totalLabel: t('usage.records', { count: data === null ? 0 : data.total }),
    pages: data === null ? 1 : Math.max(1, Math.ceil(data.total / data.page_size)),
    stats: data === null ? [] : [
      { label: t('usage.totalCost'), value: money(data.summary.cost_usd) },
      { label: t('usage.invoiceCost'), value: money(data.summary.average_invoice_cost_usd) },
      { label: t('usage.pages'), value: String(data.summary.pages) },
    ],
    daily: data === null ? [] : data.daily.map(day => ({ ...day,
      operations: Object.fromEntries(Object.entries(day.operations).map(([operation, cost]) => [operation, Number(cost)])),
      totalLabel: money(day.cost_usd),
      dateLabel: new Date(`${day.date}T00:00:00`).toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' }),
      breakdown: Object.entries(day.operations).filter(([, cost]) => Number(cost) > 0).sort((first, second) => Number(second[1]) - Number(first[1])).map(([operation, cost]) => ({ operation: t(operation === 'merge' ? 'usage.historicalMerge' : `pipeline.stages.${operation as StageId}`), cost: money(cost), color: phaseColors[operation as UsageOperation] })),
    })),
    records: data === null ? [] : data.records.map(record => ({ ...record,
      operation: t(record.operation === 'merge' ? 'usage.historicalMerge' : `pipeline.stages.${record.operation as StageId}`),
      color: phaseColors[record.operation as UsageOperation],
      providerName: record.provider === 'mistral' ? 'Mistral' : record.provider === 'openrouter' ? 'OpenRouter' : record.provider,
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
      previous: t('usage.previous'), next: t('usage.next'),
      retry: t('invoices.retry'),
    },
  }
}
