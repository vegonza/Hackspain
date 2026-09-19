import { Badge } from '@/components/ui/badge'
import type { PaymentDecision } from '@/api/invoices'

interface Props {
  classification: PaymentDecision['classification'] | null
  label: string
}

export function InvoiceDecisionBadge({ classification, label }: Props) {
  return <Badge variant="secondary" className="invoice-decision-badge" data-decision={classification}>{label}</Badge>
}
