import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { DocumentErp } from '@/components/documents/DocumentErp'
import { ErpLinkedDocuments } from '@/components/erp/ErpLinkedDocuments'
import type { useErpSnapshot } from '@/hooks/useErpSnapshot'

type Props = Pick<ReturnType<typeof useErpSnapshot>, 'loading' | 'detailTitle' | 'detailRows' | 'linkedDocuments' | 'onNavigate' | 'labels'>

export function ErpEntryDetails({ loading, detailTitle, detailRows, linkedDocuments, onNavigate, labels }: Props) {
  return (
    <>
      <header className="document-sidebar-header">
        <Button variant="ghost" size="icon-sm" asChild>
          <a href="/erp" onClick={onNavigate} aria-label={labels.back}><ArrowLeft size={16} /></a>
        </Button>
        {detailTitle !== null
          ? <Tooltip text={detailTitle} onlyWhenTruncated asChild><h1>{detailTitle}</h1></Tooltip>
          : loading ? <Skeleton className="h-4 flex-1" /> : <h1>{labels.entryUnavailable}</h1>}
      </header>
      {(loading || detailTitle !== null) && <div className="documents-table-scroll">
        <DocumentErp loading={loading} rows={detailRows} />
        <ErpLinkedDocuments title={labels.linkedDocuments} empty={labels.noLinkedDocuments} loading={loading} documents={linkedDocuments} onNavigate={onNavigate} />
      </div>}
    </>
  )
}
