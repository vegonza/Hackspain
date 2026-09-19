import type { InvoiceFeatures as InvoiceFeaturesData } from '@/api/documents'
import { Tooltip } from '@/components/ui/tooltip'
import type { useDocuments } from '@/hooks/useDocuments'

interface Labels {
  notes: string
  uncertainties: string
  invoiceNumber: string
  invoiceDate: string
  purchaseOrder: string
  supplierName: string
  supplierNif: string
  iban: string
  lineItems: string
  taxBase: string
  vatRate: string
  vatAmount: string
  total: string
}

interface Props {
  title: string
  features: InvoiceFeaturesData
  amounts: NonNullable<ReturnType<typeof useDocuments>['featureAmounts']>
  labels: Labels
}

export function InvoiceFeatures({ title, features, amounts, labels }: Props) {
  return (
    <section className="document-data" aria-label={title}>
      <header className="review-header"><h2>{title}</h2></header>
      <div className="features-view">
        <dl className="features-grid">
          <div><dt>{labels.supplierName}</dt><Tooltip text={features.supplier_name} onlyWhenTruncated asChild><dd>{features.supplier_name}</dd></Tooltip></div>
          <div><dt>{labels.invoiceNumber}</dt><Tooltip text={features.invoice_number} onlyWhenTruncated asChild><dd>{features.invoice_number}</dd></Tooltip></div>
          <div><dt>{labels.invoiceDate}</dt><Tooltip text={features.invoice_date} onlyWhenTruncated asChild><dd>{features.invoice_date}</dd></Tooltip></div>
          <div><dt>{labels.purchaseOrder}</dt><Tooltip text={features.purchase_order} onlyWhenTruncated asChild><dd>{features.purchase_order}</dd></Tooltip></div>
          <div><dt>{labels.supplierNif}</dt><Tooltip text={features.supplier_nif} onlyWhenTruncated asChild><dd>{features.supplier_nif}</dd></Tooltip></div>
          <div><dt>{labels.iban}</dt><Tooltip text={features.iban} onlyWhenTruncated asChild><dd>{features.iban}</dd></Tooltip></div>
          <div><dt>{labels.taxBase}</dt><Tooltip text={amounts.taxBase} onlyWhenTruncated asChild><dd>{amounts.taxBase}</dd></Tooltip></div>
          <div><dt>{labels.vatRate}</dt><Tooltip text={amounts.vatRate} onlyWhenTruncated asChild><dd>{amounts.vatRate}</dd></Tooltip></div>
          <div><dt>{labels.vatAmount}</dt><Tooltip text={amounts.vatAmount} onlyWhenTruncated asChild><dd>{amounts.vatAmount}</dd></Tooltip></div>
          <div><dt>{labels.total}</dt><Tooltip text={amounts.total} onlyWhenTruncated asChild><dd>{amounts.total}</dd></Tooltip></div>
          <div>
            <dt>{labels.lineItems}</dt>
            <Tooltip text={amounts.lineItems} onlyWhenTruncated asChild><dd>{amounts.lineItems}</dd></Tooltip>
          </div>
          {features.notes.length > 0 && <div className="features-notes"><dt>{labels.notes}</dt><dd>{features.notes.map((note, index) => <p key={index}>{note}</p>)}</dd></div>}
          {features.uncertainties.length > 0 && <div className="features-notes"><dt>{labels.uncertainties}</dt><dd>{features.uncertainties.map((uncertainty, index) => <p key={index}>{uncertainty}</p>)}</dd></div>}
        </dl>
      </div>
    </section>
  )
}
