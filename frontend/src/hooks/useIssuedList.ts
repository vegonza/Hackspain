import { useRef, useState, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { downloadIssuedInvoice, type IssuedInvoiceSummary } from '@/api/issued'
import { navigate, followLink } from '@/hooks/useAppRoute'
import { normalizeSearch, type BillingSort, type BillingRow } from '@/hooks/invoiceBilling'
import { formatAmount, formatDateShort } from '@/lib/format'

export function useIssuedList(invoices: IssuedInvoiceSummary[], period: string, search: string, sort: { column: BillingSort | null; direction: 'asc' | 'desc' }) {
  const { t } = useTranslation()
  const [downloading, setDownloading] = useState<string | null>(null)
  const downloadInFlight = useRef(false)
  const words = normalizeSearch(search).trim().split(/\s+/)
  const filtered = invoices.filter(invoice => (period === 'all' || invoice.issue_date.startsWith(period))
    && words.every(word => normalizeSearch([invoice.id, invoice.invoice_number, invoice.client.name, invoice.client.tax_id, ...invoice.items.map(line => line.description)].join(' ')).includes(word)))
    .sort((left, right) => {
      if (sort.column === null) return 0
      const result = sort.column === 'amount' ? Number(left.base_amount) - Number(right.base_amount)
        : sort.column === 'review' ? t(`issued.status.${left.status}`).localeCompare(t(`issued.status.${right.status}`), 'es')
        : (sort.column === 'date' ? left.issue_date.localeCompare(right.issue_date) : left.client.name.localeCompare(right.client.name, 'es'))
      return (sort.direction === 'asc' ? result : -result) || left.id.localeCompare(right.id)
    })
  async function download(invoice: IssuedInvoiceSummary): Promise<void> {
    if (downloadInFlight.current) return
    downloadInFlight.current = true
    setDownloading(invoice.id)
    try {
      const blob = await downloadIssuedInvoice(invoice.id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url; anchor.download = `${invoice.invoice_number}.pdf`; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      // The API client displays download errors.
    } finally { downloadInFlight.current = false; setDownloading(null) }
  }
  return {
    rows: filtered.map(invoice => ({
      id: invoice.id, partyName: invoice.client.name, logo: invoice.client.logo_url === '' ? undefined : invoice.client.logo_url,
      initials: invoice.client.name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('').toLocaleUpperCase('es-ES'),
      secondary: [invoice.invoice_number, ...invoice.items.map(line => line.description)].join(' · '),
      date: formatDateShort(`${invoice.issue_date}T12:00:00`, 'es-ES'),
      amount: formatAmount(Number(invoice.base_amount), 'EUR'), gross: t('billing.grossAmount', { amount: formatAmount(Number(invoice.total_amount), 'EUR') }),
      badge: {
        label: t(`issued.status.${invoice.status}`), description: t(`issued.status.${invoice.status}`),
        tone: invoice.status === 'paid' ? 'success' : invoice.status === 'issued' ? 'warning' : 'neutral',
        icon: invoice.status === 'issuing' ? 'clock' : null,
        processing: false, status: invoice.status, classification: null,
      } satisfies BillingRow['badge'],
      originalAmount: null, canOpen: true, href: `/invoices/issued/${invoice.id}`,
      canDownload: invoice.pdf_path !== null, onDownload: () => void download(invoice),
    })),
    downloading, onNavigate: (event: MouseEvent<HTMLAnchorElement>) => { event.stopPropagation(); followLink(event) }, onCreate: () => navigate('/invoices/issued/new'),
    onOpen: (id: string) => navigate(`/invoices/issued/${id}`),
    labels: { title: t('issued.section'), received: t('issued.received'), create: t('issued.new'), client: t('issued.clientInvoice'), status: t('issued.state'), empty: search.trim() === '' ? t('issued.empty') : t('invoices.noResults'), failed: t('issued.failed'), downloadPdf: t('issued.download'), actions: t('common.actions') },
  }
}
