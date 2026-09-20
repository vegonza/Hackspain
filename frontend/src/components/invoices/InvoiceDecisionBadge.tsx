import { Badge } from '@/components/ui/badge'
import { Check, ChevronDown, LoaderCircle, X } from 'lucide-react'
import { DropdownMenu } from 'radix-ui'
import type { PaymentDecision } from '@/api/invoices'

interface Props {
  classification: PaymentDecision['classification'] | null
  label: string
  resolution?: {
    busy: boolean
    payLabel: string
    noPayLabel: string
    onResolve: (classification: 'PAGAR' | 'NO_PAGAR') => Promise<void>
  }
}

export function InvoiceDecisionBadge({ classification, label, resolution }: Props) {
  if (classification === 'ESCALAR' && resolution !== undefined) {
    return <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger asChild>
        <Badge variant="secondary" className="invoice-decision-badge cursor-pointer hover:brightness-95 disabled:cursor-default disabled:opacity-60" data-decision={classification} asChild>
          <button type="button" disabled={resolution.busy} aria-busy={resolution.busy}>
            {label}{resolution.busy ? <LoaderCircle className="animate-spin" aria-hidden="true" /> : <ChevronDown aria-hidden="true" />}
          </button>
        </Badge>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className="invoice-actions-menu" align="end" sideOffset={6} collisionPadding={8}>
          <DropdownMenu.Item className="invoice-action-option" disabled={resolution.busy} onSelect={() => void resolution.onResolve('PAGAR')}>
            <Check size={15} aria-hidden="true" />{resolution.payLabel}
          </DropdownMenu.Item>
          <DropdownMenu.Item className="invoice-action-option" disabled={resolution.busy} onSelect={() => void resolution.onResolve('NO_PAGAR')}>
            <X size={15} aria-hidden="true" />{resolution.noPayLabel}
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  }
  return <Badge variant="secondary" className="invoice-decision-badge" data-decision={classification}>{label}</Badge>
}
