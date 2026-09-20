import { Download, Ellipsis, LoaderCircle, RotateCcw, Trash2 } from 'lucide-react'
import { DropdownMenu, Popover } from 'radix-ui'
import { Button } from '@/components/ui/button'
import { useInvoiceActionsMenu } from '@/hooks/useInvoiceActionsMenu'

type Props = {
  labels: { actions: string; redo: string; delete: string; downloadPdf: string }
  redoConfirmation: string
  deleteConfirmation: string
  redoDisabled: boolean
  deleteDisabled: boolean
  downloadDisabled: boolean
  downloading: boolean
  onRedo: () => void
  onDelete: () => void
  onDownload: () => void
}

export function InvoiceActionsMenu({ labels, redoConfirmation, deleteConfirmation, redoDisabled, deleteDisabled, downloadDisabled, downloading, onRedo, onDelete, onDownload }: Props) {
  const { trigger, ...menu } = useInvoiceActionsMenu(onRedo, onDelete, redoDisabled, deleteDisabled)
  return <Popover.Root open={menu.confirmation.open} onOpenChange={menu.confirmation.onOpenChange}>
    <DropdownMenu.Root modal={false}>
      <Popover.Anchor asChild><DropdownMenu.Trigger asChild>
        <Button ref={trigger} variant="ghost" size="icon-sm" aria-label={labels.actions}>
          {downloading ? <LoaderCircle size={16} className="animate-spin" /> : <Ellipsis size={16} />}
        </Button>
      </DropdownMenu.Trigger></Popover.Anchor>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className="invoice-actions-menu" align="end" sideOffset={6} collisionPadding={8}
          onCloseAutoFocus={menu.onMenuCloseAutoFocus}>
          <DropdownMenu.Item className="invoice-action-option" disabled={redoDisabled} onSelect={menu.onRedo}><RotateCcw size={15} />{labels.redo}</DropdownMenu.Item>
          <DropdownMenu.Item className="invoice-action-option" disabled={downloadDisabled} onSelect={onDownload}><Download size={15} />{labels.downloadPdf}</DropdownMenu.Item>
          <DropdownMenu.Separator className="invoice-actions-separator" />
          <DropdownMenu.Item className="invoice-action-option invoice-action-delete" disabled={deleteDisabled} onSelect={menu.onDelete}><Trash2 size={15} />{labels.delete}</DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
    <Popover.Portal>
      <Popover.Content className="action-confirmation" align="end" sideOffset={6} collisionPadding={8}
        onFocusOutside={menu.confirmation.onFocusOutside} onCloseAutoFocus={menu.onConfirmationCloseAutoFocus}
        aria-label={menu.action === 'redo' ? labels.redo : labels.delete} aria-describedby={menu.confirmation.descriptionId}>
        <p id={menu.confirmation.descriptionId}>{menu.action === 'redo' ? redoConfirmation : deleteConfirmation}</p>
        <div className="confirmation-actions">
          <button type="button" onClick={menu.confirmation.cancel}>{menu.confirmation.cancelLabel}</button>
          <button type="button" className={`confirm-${menu.action}`} disabled={menu.disabled} onClick={menu.confirmation.confirm}>
            {menu.action === 'delete' ? labels.delete : labels.redo}
          </button>
        </div>
      </Popover.Content>
    </Popover.Portal>
  </Popover.Root>
}
