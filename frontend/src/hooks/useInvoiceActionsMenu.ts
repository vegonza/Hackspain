import { useRef, useState } from 'react'
import { useConfirmPopover } from '@/hooks/useConfirmPopover'

export function useInvoiceActionsMenu(onRedo: () => void, onDelete: () => void, redoDisabled: boolean, deleteDisabled: boolean) {
  const [action, setAction] = useState<'redo' | 'delete'>('redo')
  const trigger = useRef<HTMLButtonElement>(null)
  const disabled = action === 'redo' ? redoDisabled : deleteDisabled
  const confirmation = useConfirmPopover(action === 'redo' ? onRedo : onDelete, disabled)

  return {
    action, disabled, trigger, confirmation,
    onRedo: () => { setAction('redo'); confirmation.onOpenChange(true) },
    onDelete: () => { setAction('delete'); confirmation.onOpenChange(true) },
    onMenuCloseAutoFocus: (event: Event) => { if (confirmation.open) event.preventDefault() },
    onConfirmationCloseAutoFocus: (event: Event) => {
      event.preventDefault()
      if (trigger.current !== null) trigger.current.focus()
    },
  }
}
