import { Pencil, Trash2 } from 'lucide-react'
import { ConfirmButton } from '@/components/ui/confirm-button'

interface Props {
  name: string
  confirmation: string
  disabled: boolean
  onEdit: () => void
  onDelete: () => void
  labels: { edit: string; delete: string }
}

export function RowActions({ name, disabled, onEdit, onDelete, labels, confirmation }: Props) {
  return <div className="invoice-table-action">
    <button type="button" className="invoice-edit" disabled={disabled} onClick={onEdit} aria-label={`${labels.edit}: ${name}`} title={labels.edit}>
      <Pencil size={15} />
    </button>
    <ConfirmButton label={labels.delete} confirmation={confirmation} disabled={disabled} onConfirm={onDelete} icon={Trash2} variant="delete" />
  </div>
}
