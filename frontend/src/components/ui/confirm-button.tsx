import type { ReactElement } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Popover } from 'radix-ui'
import { useConfirmPopover } from '@/hooks/useConfirmPopover'

interface Props {
  trigger?: ReactElement
  label: string
  confirmation: string
  disabled: boolean
  onConfirm: () => void
  icon: LucideIcon
  variant: 'delete' | 'redo'
}

export function ConfirmButton({ label, confirmation, disabled, onConfirm, icon: Icon, variant, trigger }: Props) {
  const controller = useConfirmPopover(onConfirm, disabled)
  return (
    <Popover.Root open={controller.open} onOpenChange={controller.onOpenChange}>
      <Popover.Trigger asChild>
        {trigger === undefined ? <button type="button" className={`invoice-${variant}`} disabled={disabled} aria-label={label} title={label}>
          <Icon size={15} />
        </button> : trigger}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="action-confirmation" align="end" sideOffset={6} collisionPadding={8}
          onFocusOutside={controller.onFocusOutside}
          sticky="always" aria-label={label} aria-describedby={controller.descriptionId}>
          <p id={controller.descriptionId}>{confirmation}</p>
          <div className="confirmation-actions">
            <button type="button" onClick={controller.cancel}>{controller.cancelLabel}</button>
            <button type="button" className={`confirm-${variant}`} disabled={disabled} onClick={controller.confirm}>{label}</button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
