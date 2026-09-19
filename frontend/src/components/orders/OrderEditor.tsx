import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import type { useOrders } from '@/hooks/useOrders'

type Props = Pick<ReturnType<typeof useOrders>, 'draft' | 'editingId' | 'saving' | 'onChange' | 'onSave' | 'onCancel' | 'labels'>

export function OrderEditor({ draft, editingId, saving, onChange, onSave, onCancel, labels }: Props) {
  return <Dialog open onOpenChange={onCancel}>
    <DialogContent closeLabel={labels.close} aria-describedby={undefined} className="max-w-xl">
    <DialogTitle className="pr-8 text-lg font-semibold">{editingId === null ? labels.add : labels.edit}</DialogTitle>
    <form onSubmit={onSave}>
    <fieldset disabled={saving} className="grid gap-4 sm:grid-cols-2">
      {(['order_id', 'supplier_id', 'status'] as const).map(field => <label key={field} className="grid gap-1.5 text-xs font-medium">
        {labels[field]}<Input required value={draft[field]} readOnly={field === 'order_id' && editingId !== null}
          onChange={event => onChange(field, event.target.value)} />
      </label>)}
      <label className="grid gap-1.5 text-xs font-medium">{labels.tax_id}
        <Input value={draft.tax_id ?? ''} onChange={event => onChange('tax_id', event.target.value === '' ? null : event.target.value)} />
      </label>
      <label className="grid gap-1.5 text-xs font-medium">{labels.amount}
        <Input type="number" required step="0.01" value={draft.amount} onChange={event => onChange('amount', event.target.value)} />
      </label>
      <label className="grid gap-1.5 text-xs font-medium">{labels.date}
        <Input type="date" required value={draft.date} onChange={event => onChange('date', event.target.value)} />
      </label>
    </fieldset>
    <div className="mt-4 flex justify-end gap-2">
      <Button type="button" variant="outline" onClick={onCancel}>{labels.cancel}</Button>
      <Button type="submit" disabled={saving}>{saving ? labels.saving : labels.save}</Button>
    </div>
    </form>
    </DialogContent>
  </Dialog>
}
