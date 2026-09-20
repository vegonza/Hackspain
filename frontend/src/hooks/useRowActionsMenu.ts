import { useRef } from 'react'
import { useConfirmPopover } from '@/hooks/useConfirmPopover'

export interface RowDeleteAction {
  label: string
  confirmation: string
  onDelete: () => void
}

export function useRowActionsMenu(deletion: RowDeleteAction | null, disabled: boolean) {
  const trigger = useRef<HTMLButtonElement>(null)
  const confirmation = useConfirmPopover(() => { if (deletion !== null) deletion.onDelete() }, disabled || deletion === null)

  return {
    trigger,
    confirmation,
    onDelete: () => confirmation.onOpenChange(true),
    onMenuCloseAutoFocus: (event: Event) => { if (confirmation.open) event.preventDefault() },
    onConfirmationCloseAutoFocus: (event: Event) => {
      event.preventDefault()
      if (trigger.current !== null) trigger.current.focus()
    },
  }
}
