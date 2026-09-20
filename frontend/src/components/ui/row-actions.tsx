import { Ellipsis, Pencil, Trash2 } from 'lucide-react'
import { DropdownMenu, Popover } from 'radix-ui'
import { Button } from '@/components/ui/button'
import { useRowActionsMenu, type RowDeleteAction } from '@/hooks/useRowActionsMenu'

interface Props {
  name: string
  disabled: boolean
  onEdit: () => void
  deletion: RowDeleteAction | null
  labels: { actions: string; edit: string }
}

export function RowActions({ name, disabled, onEdit, deletion, labels }: Props) {
  const { trigger, confirmation: deleteConfirmation, ...menu } = useRowActionsMenu(deletion, disabled)
  return <div className="invoice-table-action">
    <Popover.Root open={deleteConfirmation.open} onOpenChange={deleteConfirmation.onOpenChange}>
      <DropdownMenu.Root modal={false}>
        <Popover.Anchor asChild><DropdownMenu.Trigger asChild>
          <Button ref={trigger} variant="ghost" size="icon-sm" aria-label={`${labels.actions}: ${name}`} disabled={disabled}>
            <Ellipsis size={16} />
          </Button>
        </DropdownMenu.Trigger></Popover.Anchor>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="invoice-actions-menu" align="end" sideOffset={6} collisionPadding={8}
            onCloseAutoFocus={menu.onMenuCloseAutoFocus}>
            <DropdownMenu.Item className="invoice-action-option" onSelect={onEdit}><Pencil size={15} />{labels.edit}</DropdownMenu.Item>
            {deletion !== null && <><DropdownMenu.Separator className="invoice-actions-separator" />
            <DropdownMenu.Item className="invoice-action-option invoice-action-delete" onSelect={menu.onDelete}><Trash2 size={15} />{deletion.label}</DropdownMenu.Item></>}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      {deletion !== null && <Popover.Portal>
        <Popover.Content className="action-confirmation" align="end" sideOffset={6} collisionPadding={8}
          onFocusOutside={deleteConfirmation.onFocusOutside} onCloseAutoFocus={menu.onConfirmationCloseAutoFocus}
          aria-label={deletion.label} aria-describedby={deleteConfirmation.descriptionId}>
          <p id={deleteConfirmation.descriptionId}>{deletion.confirmation}</p>
          <div className="confirmation-actions">
            <button type="button" onClick={deleteConfirmation.cancel}>{deleteConfirmation.cancelLabel}</button>
            <button type="button" className="confirm-delete" disabled={disabled} onClick={deleteConfirmation.confirm}>{deletion.label}</button>
          </div>
        </Popover.Content>
      </Popover.Portal>}
    </Popover.Root>
  </div>
}
