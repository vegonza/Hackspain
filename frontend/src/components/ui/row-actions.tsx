import { Ellipsis, Pencil, Trash2 } from 'lucide-react'
import { DropdownMenu } from 'radix-ui'
import { Button } from '@/components/ui/button'
import { ConfirmButton } from '@/components/ui/confirm-button'

interface Props {
  name: string
  confirmation: string
  disabled: boolean
  onEdit: () => void
  onDelete: () => void
  labels: { actions: string; edit: string; delete: string }
}

export function RowActions({ name, disabled, onEdit, onDelete, labels, confirmation }: Props) {
  return <DropdownMenu.Root modal={false}>
    <DropdownMenu.Trigger asChild>
      <Button variant="ghost" size="icon-sm" disabled={disabled} aria-label={`${labels.actions}: ${name}`}><Ellipsis size={16} /></Button>
    </DropdownMenu.Trigger>
    <DropdownMenu.Portal>
      <DropdownMenu.Content align="end" sideOffset={4} className="z-50 min-w-40 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
        <DropdownMenu.Item onSelect={onEdit} disabled={disabled} className="flex min-h-8 cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-[13px] outline-none focus:bg-hover data-[disabled]:pointer-events-none data-[disabled]:opacity-50">
          <Pencil size={14} />{labels.edit}
        </DropdownMenu.Item>
        <ConfirmButton label={labels.delete} confirmation={confirmation} disabled={disabled} onConfirm={onDelete} icon={Trash2} variant="delete"
          trigger={<DropdownMenu.Item onSelect={event => event.preventDefault()} disabled={disabled}
            className="flex min-h-8 cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-[13px] text-destructive outline-none focus:bg-hover data-[disabled]:pointer-events-none data-[disabled]:opacity-50">
            <Trash2 size={14} />{labels.delete}
          </DropdownMenu.Item>} />

      </DropdownMenu.Content>
    </DropdownMenu.Portal>
  </DropdownMenu.Root>
}
