import { ChevronRight, CircleAlert } from 'lucide-react'
import type { InvoiceExtraction as InvoiceExtractionData } from '@/api/invoices'
import { Tooltip } from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { InvoiceIdentifierTooltip } from '@/components/invoices/InvoiceIdentifierTooltip'
import type { useInvoices } from '@/hooks/useInvoices'

interface Labels {
  inferred: string
  notes: string
  uncertainties: string
  invoiceNumber: string
  invoiceDate: string
  purchaseOrder: string
  supplierName: string
  supplierNif: string
  iban: string
  lineItems: string
  showMore: string
  showLess: string
  taxBase: string
  vatRate: string
  vatAmount: string
  total: string
}

interface Props {
  title: string
  extraction: InvoiceExtractionData
  amounts: NonNullable<ReturnType<typeof useInvoices>['featureAmounts']>
  labels: Labels
  identifierTrace: ReturnType<typeof useInvoices>['identifierTrace']
}

export function InvoiceExtraction({ title, extraction, amounts, labels, identifierTrace }: Props) {
  return (
    <section className="invoice-data" aria-label={title}>
      <div className="extraction-view">
        <dl className="extraction-grid">
          <div><dt>{labels.supplierName}</dt><Tooltip text={extraction.supplier_name} onlyWhenTruncated asChild><dd>{extraction.supplier_name}</dd></Tooltip></div>
          <div><dt>{labels.invoiceNumber}</dt><Tooltip text={extraction.invoice_number} onlyWhenTruncated asChild><dd>{extraction.invoice_number}</dd></Tooltip></div>
          <div><dt>{labels.invoiceDate}</dt><Tooltip text={extraction.invoice_date} onlyWhenTruncated asChild><dd>{extraction.invoice_date}</dd></Tooltip></div>
          <div><dt>{labels.purchaseOrder}</dt><Tooltip text={extraction.purchase_order} onlyWhenTruncated asChild><dd>{extraction.purchase_order}</dd></Tooltip></div>
          <div><dt>{labels.supplierNif}</dt>
            {identifierTrace.supplier_nif === null
              ? <Tooltip text={extraction.supplier_nif} onlyWhenTruncated asChild><dd>{extraction.supplier_nif}</dd></Tooltip>
              : <dd><Tooltip text={<InvoiceIdentifierTooltip {...identifierTrace.supplier_nif} />} asChild><Badge variant="outline" className="h-auto max-w-full gap-1.5 rounded-md border-amber-200 bg-amber-50 px-2 py-0.5 align-middle text-sm font-normal text-amber-800" aria-label={`${labels.inferred}: ${extraction.supplier_nif}`}><CircleAlert size={13} className="shrink-0 text-amber-600" aria-hidden="true" /><span className="truncate">{extraction.supplier_nif}</span></Badge></Tooltip></dd>}
          </div>
          <div><dt>{labels.iban}</dt>
            {identifierTrace.iban === null
              ? <Tooltip text={extraction.iban} onlyWhenTruncated asChild><dd>{extraction.iban}</dd></Tooltip>
              : <dd><Tooltip text={<InvoiceIdentifierTooltip {...identifierTrace.iban} />} asChild><Badge variant="outline" className="h-auto max-w-full gap-1.5 rounded-md border-amber-200 bg-amber-50 px-2 py-0.5 align-middle text-sm font-normal text-amber-800" aria-label={`${labels.inferred}: ${extraction.iban}`}><CircleAlert size={13} className="shrink-0 text-amber-600" aria-hidden="true" /><span className="truncate">{extraction.iban}</span></Badge></Tooltip></dd>}
          </div>
          <div><dt>{labels.taxBase}</dt><Tooltip text={amounts.taxBase} onlyWhenTruncated asChild><dd>{amounts.taxBase}</dd></Tooltip></div>
          <div><dt>{labels.vatRate}</dt><Tooltip text={amounts.vatRate} onlyWhenTruncated asChild><dd>{amounts.vatRate}</dd></Tooltip></div>
          <div><dt>{labels.vatAmount}</dt><Tooltip text={amounts.vatAmount} onlyWhenTruncated asChild><dd>{amounts.vatAmount}</dd></Tooltip></div>
          <div><dt>{labels.total}</dt><Tooltip text={amounts.total} onlyWhenTruncated asChild><dd>{amounts.total}</dd></Tooltip></div>
          <div className="extraction-line-items">
            <dt>{labels.lineItems}</dt>
            <dd>
              <ul className="extraction-line-list" aria-label={labels.lineItems}>
                {amounts.lineItems.map((line, index) => (
                  <li key={index}><span>{line.description}</span><span>{line.amount}</span></li>
                ))}
              </ul>
              {amounts.canExpandLineItems && <Button type="button" variant="link" size="sm"
                className="mt-2 h-auto min-h-0 rounded-none border-0 p-0 underline cursor-pointer focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                aria-expanded={amounts.lineItemsExpanded} onClick={amounts.onToggleLineItems}>
                <ChevronRight aria-hidden="true" className={amounts.lineItemsExpanded ? 'rotate-90' : ''} />
                {amounts.lineItemsExpanded ? labels.showLess : labels.showMore}
              </Button>}
            </dd>
          </div>
          {extraction.notes.length > 0 && <div className="extraction-notes"><dt>{labels.notes}</dt><dd>{extraction.notes.map((note, index) => <p key={index}>{note}</p>)}</dd></div>}
          {extraction.uncertainties.length > 0 && <div className="extraction-notes"><dt>{labels.uncertainties}</dt><dd>{extraction.uncertainties.map((uncertainty, index) => <p key={index}>{uncertainty}</p>)}</dd></div>}
        </dl>
      </div>
    </section>
  )
}
