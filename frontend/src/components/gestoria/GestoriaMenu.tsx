import { InvoiceStatusBadge } from '@/components/invoices/InvoiceStatusBadge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { LoadingField } from '@/components/ui/loading-field'
import { Skeleton } from '@/components/ui/skeleton'
import type { useGestoria } from '@/hooks/useGestoria'

type Props = { gestoria: ReturnType<typeof useGestoria> }

export function GestoriaMenu({ gestoria: { mount, ...g } }: Props) {
  return <Dialog open={g.open} onOpenChange={g.onOpenChange}>
    <DialogContent closeLabel={g.labels.close} aria-describedby="gestoria-period">
      <div className="grid gap-1 pr-8">
        <DialogTitle className="text-lg font-semibold">{g.labels.title}</DialogTitle>
        <span id="gestoria-period" className="text-sm text-muted-foreground">{g.labels.period}</span>
      </div>
      <form ref={mount} onSubmit={g.onSubmit} className="flex flex-col gap-5">
        <label className="grid gap-2 text-sm">{g.labels.email}
          <LoadingField loading={g.loading}><Input type="email" required maxLength={254} value={g.email} onChange={event => g.onEmail(event.target.value)} disabled={g.loading || g.busy || g.failed} /></LoadingField>
        </label>
        <div className="grid gap-2" role="group" aria-labelledby="gestoria-ready">
          <span id="gestoria-ready" className="text-sm">{g.labels.ready}</span>
          <div className="flex flex-wrap gap-2" aria-live="polite">
            {g.loading ? [0, 1].map(index => <Skeleton key={index} className="h-5 w-28 rounded-full" />)
              : !g.failed && g.statuses.map(row => <InvoiceStatusBadge key={row.key} badge={row.badge}><span className="tabular-nums">{row.count}</span></InvoiceStatusBadge>)}
            {!g.loading && !g.failed && g.statuses.length === 0 && <span className="text-sm text-muted-foreground">{g.labels.empty}</span>}
          </div>
        </div>
        {g.failed && <p role="alert" className="text-sm text-destructive">{g.labels.failed}</p>}
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={g.busy} onClick={() => g.onOpenChange(false)}>{g.labels.cancel}</Button>
          <Button type="submit" disabled={g.loading || g.busy || g.failed}>{g.labels.submit}</Button></div>
      </form>
    </DialogContent>
  </Dialog>
}
