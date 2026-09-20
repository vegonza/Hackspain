import { Skeleton } from '@/components/ui/skeleton'
import type { useIssuedEditor } from '@/hooks/useIssuedEditor'

type Props = { editor: ReturnType<typeof useIssuedEditor> }
export function IssuedInvoicePreview({ editor: e }: Props) {
  return <article className="issued-preview-paper" aria-label={e.labels.preview} aria-busy={e.loading}>
    <header className="issued-preview-hero">
      <div className="min-w-0 flex-1">
        <div className="issued-preview-brand">
          {e.loading ? <><Skeleton className="size-12 shrink-0" /><Skeleton className="h-6 w-48 max-w-full" /></>
            : <>{e.companyLogo !== undefined && <img src={e.companyLogo} className="issued-preview-logo" alt="" width={48} height={48} />}
              <span>{e.company === null ? e.labels.emptyCompany : e.company.name}</span></>}
        </div>
        <div className="flex items-baseline gap-1"><h1>{e.labels.invoiceLabel} {e.invoice !== null && e.invoice.invoice_number}</h1>{e.valuesLoading && <Skeleton className="h-3 w-24" />}</div>
        <div className="text-[#66726e]">{e.valuesLoading ? <Skeleton className="h-3 w-20" /> : e.previewIssueDate}</div>
      </div>
      {e.showQr && <div className="issued-preview-qr">
        <span>{e.labels.verifactuQr}</span>
        {e.valuesLoading ? <Skeleton className="size-[32mm]" /> : e.previewQr === null ? <span className="flex size-[32mm] items-center justify-center">{e.labels.qrPending}</span> : <img src={e.previewQr} alt={e.previewQrAlt} />}
        <strong>{e.labels.verifactuLabel}</strong>
      </div>}
    </header>
    <div className="issued-preview-content">
      <div className="issued-preview-parties">
        <div><h2>{e.labels.company}</h2>{e.loading ? <div className="space-y-2"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-3 w-20" /><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-2/3" /></div>
          : e.company === null ? <p>{e.labels.emptyCompany}</p> : <><strong>{e.company.name}</strong><p>{e.company.tax_id}</p><p>{e.company.address}</p><p>{e.company.email}</p></>}</div>
        <div><h2>{e.labels.client}</h2>{e.valuesLoading ? <div className="space-y-2"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-3 w-20" /><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-2/3" /></div>
          : e.client === null ? <p>{e.labels.emptyClient}</p> : <><strong>{e.client.name}</strong><p>{e.client.tax_id}</p><p>{e.client.address}</p><p>{e.client.email}</p></>}</div>
      </div>
      <div className="issued-preview-dates">
        <div className="flex items-center gap-1">{e.labels.issueDate}: {e.valuesLoading ? <Skeleton className="h-3 w-20" /> : e.previewIssueDate}</div>
        <div className="flex items-center gap-1">{e.labels.dueDate}: {e.valuesLoading ? <Skeleton className="h-3 w-20" /> : e.previewDueDate}</div>
      </div>
      <h2 className="issued-preview-section-title">{e.labels.concepts}</h2>
      <table><thead><tr><th>{e.labels.description}</th><th>{e.labels.quantity}</th><th>{e.labels.unitPrice}</th><th>{e.labels.taxRate}</th><th>{e.labels.amount}</th></tr></thead>
        <tbody>{e.valuesLoading ? <tr><td><Skeleton className="h-3 w-3/4" /></td>{Array.from({ length: 4 }, (_, index) => <td key={index}><Skeleton className="ml-auto h-3 w-3/4" /></td>)}</tr>
          : e.previewLines.map((line, index) => <tr key={index}><td>{line.description}</td><td>{line.quantity}</td><td>{line.price}</td><td>{line.tax_rate}%</td><td>{line.amount}</td></tr>)}</tbody></table>
      <dl className="issued-preview-totals">{(['base', 'tax', 'total'] as const).map(field => <div key={field}><dt>{e.labels[field]}</dt><dd>{e.valuesLoading ? <Skeleton className="h-3 w-16" /> : e.totals[field]}</dd></div>)}</dl>
      {e.company !== null && (e.company.payment_method !== '' || e.company.iban !== '') && <div className="issued-preview-payment"><h2 className="issued-preview-section-title">{e.labels.paymentInfo}</h2>{e.company.payment_method !== '' && <p><strong>{e.labels.paymentMethod}:</strong> {e.company.payment_method}</p>}{e.company.iban !== '' && <p><strong>{e.labels.iban}:</strong> {e.company.iban}</p>}</div>}
      <div className="issued-preview-notes">{e.valuesLoading ? <Skeleton className="h-3 w-3/4" /> : e.draft.notes}</div>
      {e.testRegistration !== null && <div className="issued-preview-payment"><h2 className="issued-preview-section-title">{e.testRegistration.title}</h2><p>{e.testRegistration.issuer}</p><p>{e.testRegistration.client}</p></div>}
    </div>
    <footer className="issued-preview-footer"><span>{e.labels.thanks}</span>{e.loading ? <Skeleton className="h-3 w-28" /> : <span>{e.company !== null && e.company.name}</span>}</footer>
  </article>
}
