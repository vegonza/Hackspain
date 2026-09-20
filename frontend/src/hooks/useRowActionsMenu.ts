import { useRef } from 'react'
import { useConfirmPopover } from '@/hooks/useConfirmPopover'

export function useRowActionsMenu(onDelete: () => void, disabled: boolean) {
  const trigger = useRef<HTMLButtonElement>(null)
  const confirmation = useConfirmPopover(onDelete, disabled)

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
