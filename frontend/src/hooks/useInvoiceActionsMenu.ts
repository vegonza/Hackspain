import { useRef, useState } from 'react'
import { useConfirmPopover } from '@/hooks/useConfirmPopover'

export interface InvoiceManagementActions {
  redoLabel: string
  deleteLabel: string
  redoConfirmation: string
  deleteConfirmation: string
  redoDisabled: boolean
  deleteDisabled: boolean
  onRedo: () => void
  onDelete: () => void
}

export function useInvoiceActionsMenu(management: InvoiceManagementActions | null) {
  const [action, setAction] = useState<'redo' | 'delete'>('redo')
  const trigger = useRef<HTMLButtonElement>(null)
  const disabled = management === null || (action === 'redo' ? management.redoDisabled : management.deleteDisabled)
  const confirmation = useConfirmPopover(() => {
    if (management !== null) (action === 'redo' ? management.onRedo : management.onDelete)()
  }, disabled)

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
