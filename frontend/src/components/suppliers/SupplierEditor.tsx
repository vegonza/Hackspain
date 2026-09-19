import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import type { useSuppliers } from '@/hooks/useSuppliers'

type Props = Pick<ReturnType<typeof useSuppliers>, 'draft' | 'editingId' | 'saving' | 'onChange' | 'onSave' | 'onCancel' | 'labels'>

export function SupplierEditor({ draft, editingId, saving, onChange, onSave, onCancel, labels }: Props) {
  return <Dialog open onOpenChange={onCancel}>
    <DialogContent closeLabel={labels.close} aria-describedby={undefined} className="max-w-xl">
    <DialogTitle className="pr-8 text-lg font-semibold">{editingId === null ? labels.add : labels.edit}</DialogTitle>
    <form onSubmit={onSave}>
    <fieldset disabled={saving} className="grid gap-4 sm:grid-cols-2">
      {(['supplier_id', 'legal_name', 'tax_id', 'iban', 'city'] as const).map(field => <label key={field} className="grid gap-1.5 text-xs font-medium">
        {labels[field]}<Input required value={draft[field]} readOnly={field === 'supplier_id' && editingId !== null}
          onChange={event => onChange(field, event.target.value)} />
      </label>)}
      <label className="grid gap-1.5 text-xs font-medium">{labels.payment_terms_days}
        <Input type="number" required min={0} step={1} value={Number.isNaN(draft.payment_terms_days) ? '' : draft.payment_terms_days}
          onChange={event => onChange('payment_terms_days', event.target.valueAsNumber)} />
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
