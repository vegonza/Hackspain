import type { InvoiceFeatures as InvoiceFeaturesData } from '@/api/documents'
import { Tooltip } from '@/components/ui/tooltip'

interface Labels {
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
  features: InvoiceFeaturesData
  labels: Labels
}

function money(value: string): string {
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(Number(value))
}

export function InvoiceFeatures({ features, labels }: Props) {
  const lines = features.line_items.map(line => `${line.description} · ${money(line.amount)}`).join(', ')
  return (
    <div className="features-view">
      <dl className="features-grid">
        <div><dt>{labels.invoiceNumber}</dt><Tooltip text={features.invoice_number} onlyWhenTruncated asChild><dd>{features.invoice_number}</dd></Tooltip></div>
        <div><dt>{labels.invoiceDate}</dt><Tooltip text={features.invoice_date} onlyWhenTruncated asChild><dd>{features.invoice_date}</dd></Tooltip></div>
        <div><dt>{labels.purchaseOrder}</dt><Tooltip text={features.purchase_order} onlyWhenTruncated asChild><dd>{features.purchase_order}</dd></Tooltip></div>
        <div><dt>{labels.supplierName}</dt><Tooltip text={features.supplier_name} onlyWhenTruncated asChild><dd>{features.supplier_name}</dd></Tooltip></div>
        <div><dt>{labels.supplierNif}</dt><Tooltip text={features.supplier_nif} onlyWhenTruncated asChild><dd>{features.supplier_nif}</dd></Tooltip></div>
        <div><dt>{labels.iban}</dt><Tooltip text={features.iban} onlyWhenTruncated asChild><dd>{features.iban}</dd></Tooltip></div>
        <div><dt>{labels.taxBase}</dt><Tooltip text={money(features.tax_base)} onlyWhenTruncated asChild><dd>{money(features.tax_base)}</dd></Tooltip></div>
        <div><dt>{labels.vatRate}</dt><Tooltip text={`${features.vat_rate}%`} onlyWhenTruncated asChild><dd>{features.vat_rate}%</dd></Tooltip></div>
        <div><dt>{labels.vatAmount}</dt><Tooltip text={money(features.vat_amount)} onlyWhenTruncated asChild><dd>{money(features.vat_amount)}</dd></Tooltip></div>
        <div><dt>{labels.total}</dt><Tooltip text={money(features.total)} onlyWhenTruncated asChild><dd className="feature-total">{money(features.total)}</dd></Tooltip></div>
        <div className="feature-lines">
          <dt>{labels.lineItems}</dt>
          <Tooltip text={lines} onlyWhenTruncated asChild><dd>{lines}</dd></Tooltip>
        </div>
      </dl>
    </div>
  )
}
