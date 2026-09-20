import { ArrowLeft, Download, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { IssuedInvoicePreview } from '@/components/issued/IssuedInvoicePreview'
import { IssuedLinesEditor } from '@/components/issued/IssuedLinesEditor'
import { Skeleton } from '@/components/ui/skeleton'
import { LoadingField } from '@/components/ui/loading-field'
import type { useIssuedEditor } from '@/hooks/useIssuedEditor'

type Props = { editor: ReturnType<typeof useIssuedEditor> }
export function IssuedInvoiceEditor({ editor: { mount, ...e } }: Props) {
  return <section className="issued-editor" ref={mount} key={e.reload}>
    <header className="issued-editor-header"><Button variant="ghost" size="icon-sm" disabled={e.busy} aria-label={e.labels.back} onClick={e.onBack}><ArrowLeft size={18} /></Button><div className="font-semibold">{e.valuesLoading ? <Skeleton className="h-4 w-32" /> : e.title}</div>{e.status !== null && <Badge variant="secondary" className="issued-state" data-status={e.invoice === null ? 'issuing' : e.invoice.status}>{e.status}</Badge>}
      <div className="issued-editor-actions">
        {e.canSubmitVerifactu && <Button variant="outline" size="sm" disabled={e.busy} onClick={e.onRequestVerifactu}>{e.labels.verifactu}</Button>}
        {e.isNew && !e.locked ? <Button size="sm" disabled={!e.canIssue} onClick={e.onRequestIssue}>{e.labels.issue}</Button>
          : e.valuesLoading ? <Button variant="outline" size="sm" disabled><Download size={15} />{e.labels.download}</Button>
          : e.invoice === null || e.invoice.status === 'issuing' ? <Button disabled={e.busy} onClick={e.onIssue}>{e.labels.retry}</Button>
          : <><Button variant="outline" size="sm" disabled={e.busy} onClick={e.onDownload}><Download size={15} />{e.labels.download}</Button>{e.invoice !== null && e.invoice.status === 'issued' && <Button size="sm" disabled={e.busy} onClick={e.onMarkPaid}><Check size={15} />{e.labels.paid}</Button>}</>}
      </div>
    </header>
    {e.failed ? <div className="issued-load-error">{e.labels.failed}<Button variant="outline" onClick={e.onRetry}>{e.labels.retry}</Button></div>
      : <div className="issued-editor-grid" aria-busy={e.loading}>
        <form className="issued-form-panel" onSubmit={e.onSubmit}>
          <fieldset disabled={e.locked || e.busy || e.loading}>
            <label>{e.labels.client}
            <LoadingField loading={e.valuesLoading}><Select value={e.draft.client_id} onValueChange={value => e.onChange('client_id', value)} options={e.clientOptions} label={e.labels.client} placeholder={e.valuesLoading ? '' : e.labels.emptyClient} disabled={e.locked || e.busy || e.loading} /></LoadingField></label>
            <div className="issued-dates"><label>{e.labels.issueDate}<LoadingField loading={e.valuesLoading}><Input required type="date" value={e.valuesLoading ? '' : e.draft.issue_date} onChange={event => e.onChange('issue_date', event.target.value)} /></LoadingField></label>
              <label>{e.labels.dueDate}<LoadingField loading={e.valuesLoading}><Input required type="date" min={e.draft.issue_date} value={e.valuesLoading ? '' : e.draft.due_date} onChange={event => e.onChange('due_date', event.target.value)} /></LoadingField></label></div>
            <IssuedLinesEditor editor={{ ...e, mount }} />
            <label>{e.labels.notes}<LoadingField loading={e.valuesLoading}><textarea className="issued-notes-input" rows={3} maxLength={5000} value={e.valuesLoading ? '' : e.draft.notes} onChange={event => e.onChange('notes', event.target.value)} /></LoadingField></label>
          </fieldset>
          <dl className="issued-form-totals"><div><dt>{e.labels.base}</dt><dd>{e.valuesLoading ? <Skeleton className="h-4 w-16" /> : e.totals.base}</dd></div><div><dt>{e.labels.tax}</dt><dd>{e.valuesLoading ? <Skeleton className="h-4 w-16" /> : e.totals.tax}</dd></div><div><dt>{e.labels.total}</dt><dd>{e.valuesLoading ? <Skeleton className="h-4 w-16" /> : e.totals.total}</dd></div></dl>
        </form>
        <div className="issued-preview-panel"><IssuedInvoicePreview editor={{ ...e, mount }} /></div>
      </div>}
    <Dialog open={e.dialog === 'issue' || e.dialog === 'leave' || e.dialog === 'verifactu'} onOpenChange={open => { if (!open) e.onCloseDialog() }}>
      <DialogContent closeLabel={e.labels.close} aria-describedby="issued-confirm-description">
        <DialogTitle>{e.dialog === 'verifactu' ? e.labels.verifactuTitle : e.dialog === 'issue' ? e.labels.issueConfirm : e.labels.leaveTitle}</DialogTitle>
        <p id="issued-confirm-description">{e.dialog === 'verifactu' ? e.labels.verifactuDescription : e.dialog === 'issue' ? e.labels.issueDescription : e.labels.leaveDescription}</p>
        <div className="issued-dialog-actions"><Button variant="outline" onClick={e.onCloseDialog}>{e.labels.cancel}</Button><Button disabled={e.busy} onClick={e.dialog === 'verifactu' ? e.onSubmitVerifactu : e.dialog === 'issue' ? e.onIssue : e.onLeave}>{e.dialog === 'verifactu' ? e.labels.verifactu : e.dialog === 'issue' ? e.labels.issue : e.labels.leave}</Button></div>
      </DialogContent>
    </Dialog>
  </section>
}
