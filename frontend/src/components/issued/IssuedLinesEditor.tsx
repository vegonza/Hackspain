import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { LoadingField } from '@/components/ui/loading-field'
import { Input } from '@/components/ui/input'
import type { useIssuedEditor } from '@/hooks/useIssuedEditor'

type Props = { editor: ReturnType<typeof useIssuedEditor> }
export function IssuedLinesEditor({ editor: e }: Props) {
  return <div className="issued-lines">
    {e.draft.items.map((line, index) => <div className="issued-line" key={index}>
      <label className="issued-line-description">{e.labels.description}<LoadingField loading={e.valuesLoading}><Input required maxLength={2000} value={e.valuesLoading ? '' : line.description} onChange={event => e.onLineChange(index, 'description', event.target.value)} /></LoadingField></label>
      <label>{e.labels.quantity}<LoadingField loading={e.valuesLoading}><Input required inputMode="decimal" value={e.valuesLoading ? '' : line.quantity} onChange={event => e.onLineChange(index, 'quantity', event.target.value)} /></LoadingField></label>
      <label>{e.labels.unitPrice}<LoadingField loading={e.valuesLoading}><Input required inputMode="decimal" value={e.valuesLoading ? '' : line.unit_price} onChange={event => e.onLineChange(index, 'unit_price', event.target.value)} /></LoadingField></label>
      <label>{e.labels.taxRate}<LoadingField loading={e.valuesLoading}><Input required inputMode="decimal" value={e.valuesLoading ? '' : line.tax_rate} onChange={event => e.onLineChange(index, 'tax_rate', event.target.value)} /></LoadingField></label>
      <Button type="button" variant="ghost" size="icon-sm" disabled={e.draft.items.length === 1} onClick={() => e.onRemoveLine(index)} aria-label={e.labels.removeLine}><X size={15} /></Button>
    </div>)}
    <Button type="button" variant="ghost" size="sm" disabled={e.draft.items.length >= 200} onClick={e.onAddLine}><Plus size={15} />{e.labels.addLine}</Button>
  </div>
}
