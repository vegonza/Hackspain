import { CircleAlert, Clock, LoaderCircle, RotateCcw, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmButton } from '@/components/ui/confirm-button'
import { Tooltip } from '@/components/ui/tooltip'
import type { useInvoiceImports } from '@/hooks/useInvoiceImports'
import type { useInvoices } from '@/hooks/useInvoices'

type Props = Omit<ReturnType<typeof useInvoiceImports>, 'track'> & {
  onInvoiceLink: ReturnType<typeof useInvoices>['onInvoiceLink']
  onRetry: (id: string) => Promise<void>
  retryDisabled: boolean
}

export function InvoiceImportPanel({ visible, rows, completed, total, canDismiss, closeLabel, onDismiss,
  summary, onInvoiceLink, onRetry, retryDisabled }: Props) {
  if (!visible) return null
  return <section className="invoice-import-panel" aria-label={summary}>
    <header className="invoice-import-header">
      <h2 className="invoice-import-title" aria-live="polite">{summary}</h2>
      {canDismiss && <Button variant="ghost" size="icon-sm" className="invoice-import-close"
        onClick={onDismiss} aria-label={closeLabel}><X size={15} /></Button>}
      <progress className="invoice-import-progress" value={completed} max={total} aria-label={summary} />
    </header>
    <ul className="invoice-import-list">
      {rows.map(row => <li key={row.id} className="invoice-import-row" data-status={row.status}>
        <Tooltip text={row.name} onlyWhenTruncated asChild>{row.href === null
          ? <span className="invoice-import-name">{row.name}</span>
          : <a className="invoice-import-name" href={row.href} onClick={onInvoiceLink}>{row.name}</a>}</Tooltip>
        <div className="invoice-import-actions">
          <Tooltip text={row.description} asChild><Badge variant="secondary" className="invoice-table-status" data-status={row.status}>
            {(row.status === 'uploading' || row.status === 'processing') && <LoaderCircle size={13} className="upload-spinner" />}
            {row.status === 'queued' && <Clock size={13} />}
            {row.status === 'error' && <CircleAlert size={13} />}
            {row.statusLabel}
          </Badge></Tooltip>
          {row.status === 'error' && <ConfirmButton icon={RotateCcw} variant="redo" label={row.retryLabel}
            confirmation={row.retryConfirmation} disabled={retryDisabled} onConfirm={() => void onRetry(row.id)} />}
        </div>
      </li>)}
    </ul>
  </section>
}
