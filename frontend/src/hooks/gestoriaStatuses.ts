import type { TFunction } from 'i18next'
import type { GestoriaStatus } from '@/api/gestoria'
import type { BillingRow } from '@/hooks/invoiceBilling'

export function gestoriaStatusBadge(row: GestoriaStatus, t: TFunction): BillingRow['badge'] {
  const label = row.kind === 'received' ? t('billing.rowDecisions.PAGAR') : t('issued.status.paid')
  return { label, description: label, tone: 'success',
    icon: null, processing: false, status: row.kind === 'received' ? 'ready' : 'paid', classification: row.kind === 'received' ? 'PAGAR' : null }
}
