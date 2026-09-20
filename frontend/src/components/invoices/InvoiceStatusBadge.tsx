import type { ReactNode } from 'react'
import { CircleAlert, Clock, LoaderCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { BillingRow } from '@/hooks/invoiceBilling'

type Props = { badge: BillingRow['badge']; children?: ReactNode }

export function InvoiceStatusBadge({ badge, children }: Props) {
  return <Badge variant="secondary" className={badge.processing ? 'invoice-table-status' : 'invoice-decision-badge'}
    data-tone={badge.tone} data-status={badge.status} data-decision={badge.classification}>
    {badge.icon === 'spinner' && <LoaderCircle size={13} className="animate-spin" />}
    {badge.icon === 'error' && <CircleAlert size={13} />}
    {badge.icon === 'clock' && <Clock size={13} />}
    {badge.label}{children}
  </Badge>
}
