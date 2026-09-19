import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { InvoiceErp } from '@/components/invoices/InvoiceErp'
import { ErpLinkedInvoices } from '@/components/erp/ErpLinkedInvoices'
import type { useErpSnapshot } from '@/hooks/useErpSnapshot'

type Props = Pick<ReturnType<typeof useErpSnapshot>, 'loading' | 'detailTitle' | 'detailRows' | 'linkedInvoices' | 'onNavigate' | 'labels'>

export function ErpEntryDetails({ loading, detailTitle, detailRows, linkedInvoices, onNavigate, labels }: Props) {
  return (
    <>
      <header className="invoice-sidebar-header">
        <Button variant="ghost" size="icon-sm" asChild>
          <a href="/erp" onClick={onNavigate} aria-label={labels.back}><ArrowLeft size={16} /></a>
        </Button>
        {detailTitle !== null
          ? <Tooltip text={detailTitle} onlyWhenTruncated asChild><h1>{detailTitle}</h1></Tooltip>
          : loading ? <Skeleton className="h-4 flex-1" /> : <h1>{labels.entryUnavailable}</h1>}
      </header>
      {(loading || detailTitle !== null) && <div className="invoices-table-scroll">
        <InvoiceErp loading={loading} rows={detailRows} />
        <ErpLinkedInvoices title={labels.linkedInvoices} empty={labels.noLinkedInvoices} loading={loading} invoices={linkedInvoices} onNavigate={onNavigate} />
      </div>}
    </>
  )
}
