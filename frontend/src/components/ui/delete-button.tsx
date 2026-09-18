import { Trash2 } from 'lucide-react'
import { Popover } from 'radix-ui'
import { useConfirmPopover } from '@/hooks/useConfirmPopover'

interface Props {
  label: string
  confirmation: string
  disabled: boolean
  onDelete: () => void
}

export function DeleteButton({ label, confirmation, disabled, onDelete }: Props) {
  const controller = useConfirmPopover(onDelete, disabled)
  return (
    <Popover.Root open={controller.open} onOpenChange={controller.onOpenChange}>
      <Popover.Trigger asChild>
        <button type="button" className="document-delete" disabled={disabled} aria-label={label} title={label}>
          <Trash2 size={15} />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="delete-confirmation" align="end" sideOffset={6} collisionPadding={8}
          sticky="always" aria-label={label} aria-describedby={controller.descriptionId}>
          <p id={controller.descriptionId}>{confirmation}</p>
          <div className="confirmation-actions">
            <button type="button" onClick={controller.cancel}>{controller.cancelLabel}</button>
            <button type="button" className="confirm-delete" disabled={disabled} onClick={controller.confirm}>{label}</button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
