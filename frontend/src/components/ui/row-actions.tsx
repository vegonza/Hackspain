import { Ellipsis, Pencil, Trash2 } from 'lucide-react'
import { DropdownMenu } from 'radix-ui'
import { Button } from '@/components/ui/button'
import { HoldButton } from '@/components/ui/hold-button'

interface Props {
  name: string
  disabled: boolean
  onEdit: () => void
  onDelete: () => void
  labels: { actions: string; edit: string; delete: string; holdDelete: string }
}

export function RowActions({ name, disabled, onEdit, onDelete, labels }: Props) {
  return <DropdownMenu.Root>
    <DropdownMenu.Trigger asChild>
      <Button variant="ghost" size="icon-sm" disabled={disabled} aria-label={`${labels.actions}: ${name}`}><Ellipsis size={16} /></Button>
    </DropdownMenu.Trigger>
    <DropdownMenu.Portal>
      <DropdownMenu.Content align="end" sideOffset={4} className="z-50 min-w-40 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
        <DropdownMenu.Item onSelect={onEdit} disabled={disabled} className="flex min-h-8 cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-[13px] outline-none focus:bg-accent data-[disabled]:pointer-events-none data-[disabled]:opacity-50">
          <Pencil size={14} />{labels.edit}
        </DropdownMenu.Item>
        <DropdownMenu.Item asChild onSelect={event => event.preventDefault()} disabled={disabled}>
          <HoldButton onConfirm={onDelete} disabled={disabled} aria-label={labels.holdDelete}
            className="flex min-h-8 w-full cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-left text-[13px] text-destructive outline-none focus:bg-accent disabled:pointer-events-none disabled:opacity-50">
            <Trash2 size={14} /><span>{labels.delete}<span className="block text-xs text-muted-foreground">{labels.holdDelete}</span></span>
          </HoldButton>
        </DropdownMenu.Item>
      </DropdownMenu.Content>
    </DropdownMenu.Portal>
  </DropdownMenu.Root>
}
