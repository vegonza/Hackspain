import type { ComponentProps } from 'react'
import type { InvoiceExtraction } from '@/components/invoices/InvoiceExtraction'
import { Skeleton } from '@/components/ui/skeleton'

export function InvoiceExtractionSkeleton({ title, labels }: Pick<ComponentProps<typeof InvoiceExtraction>, 'title' | 'labels'>) {
  return (
    <section className="invoice-data" aria-label={title} aria-busy="true">
      <div className="extraction-view">
        <dl className="extraction-grid">
          {(['invoiceNumber', 'invoiceDate', 'purchaseOrder', 'supplierNif', 'iban', 'taxBase', 'vatRate', 'vatAmount', 'total'] as const).map((field) => (
            <div key={field}>
              <dt>{labels[field]}</dt>
              <dd><Skeleton className="h-4 w-3/4" /></dd>
            </div>
          ))}
          <div className="extraction-line-items">
            <dt>{labels.lineItems}</dt>
            <dd><ul className="extraction-line-list" aria-label={labels.lineItems}>
              {Array.from({ length: 3 }, (_, index) => <li key={index}>
                <div className="extraction-line-description"><Skeleton className="size-5 shrink-0" /><Skeleton className="h-4 w-3/4" /></div>
                <Skeleton className="h-4 w-16" />
              </li>)}
            </ul></dd>
          </div>
        </dl>
      </div>
    </section>
  )
}
