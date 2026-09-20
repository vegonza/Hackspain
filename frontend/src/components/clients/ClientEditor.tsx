import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import type { useClients } from '@/hooks/useClients'

type Props = Pick<ReturnType<typeof useClients>, 'draft' | 'editingId' | 'saving' | 'onChange' | 'onSave' | 'onCancel' | 'labels'>

export function ClientEditor({ draft, editingId, saving, onChange, onSave, onCancel, labels }: Props) {
  return <Dialog open onOpenChange={onCancel}>
    <DialogContent closeLabel={labels.close} aria-describedby={undefined} className="max-w-xl">
      <DialogTitle className="pr-8 text-lg font-semibold">{editingId === null ? labels.add : labels.edit}</DialogTitle>
      <form onSubmit={onSave}>
        <fieldset disabled={saving} className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-1.5 text-xs font-medium">{labels.name}
            <Input required maxLength={200} value={draft.name} onChange={event => onChange('name', event.target.value)} />
          </label>
          <label className="grid gap-1.5 text-xs font-medium">{labels.tax_id}
            <Input required maxLength={50} value={draft.tax_id} onChange={event => onChange('tax_id', event.target.value)} />
          </label>
          <label className="grid gap-1.5 text-xs font-medium">{labels.address}
            <Input required maxLength={500} value={draft.address} onChange={event => onChange('address', event.target.value)} />
          </label>
          <label className="grid gap-1.5 text-xs font-medium">{labels.email}
            <Input type="email" maxLength={200} value={draft.email} onChange={event => onChange('email', event.target.value)} />
          </label>
          <label className="grid gap-1.5 text-xs font-medium sm:col-span-2">{labels.logo_url}
            <Input type="text" inputMode="url" maxLength={2000} value={draft.logo_url} onChange={event => onChange('logo_url', event.target.value)} />
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
