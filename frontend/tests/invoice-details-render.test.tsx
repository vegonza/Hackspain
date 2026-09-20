import { describe, expect, mock, test } from 'bun:test'
import type { ComponentProps } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import type { InvoiceDetail } from '../src/api/invoices'
import es from '../src/locales/es/translation.json'
import maintenanceIcon from '../src/assets/categories/02-mantenimiento-reparacion.svg'
import otherIcon from '../src/assets/categories/11-otros.svg'

mock.module('../src/components/invoices/PdfViewer', () => ({
  PdfViewer: ({ url }: { url: string }) => <div data-pdf={url} />,
}))
const { InvoiceDetails } = await import('../src/components/invoices/InvoiceDetails')
type Props = ComponentProps<typeof InvoiceDetails>

const invoice: InvoiceDetail = {
  id: 'invoice-1', name: 'factura.pdf', sha256: 'hash', created_at: '2026-09-19T14:00:00Z',
  billing: null, finished_at: null, status: 'ready', pages: 1, total_cost_usd: '0.004', total_duration_ms: 2000,
  retry_attempts: 0, last_error: null, next_retry_at: null, native_text: 'Texto original de la factura',
  erp: null, erp_snapshot_id: null, verifactu: null,
  identifier_trace: { identifier_corrections: [] },
  payment_decision: { classification: 'ESCALAR', reasons: ['Revisar importe'], checks: {} },
  extraction: { invoice_number: 'FA-123', supplier_name: 'Proveedor extraído', supplier_nif: 'B12345678',
    iban: 'ES1234', invoice_date: '2026-09-19', purchase_order: 'PO-1', currency: 'EUR', line_items: [], notes: [],
    uncertainties: [], tax_base: '100', vat_rate: '21', vat_amount: '21', total: '121' },
}

const props: Props = {
  mountDetail: () => {}, invoiceName: invoice.name, supplierName: 'Proveedor extraído', supplierLogo: undefined, selectedId: invoice.id, selected: invoice,
  loading: false, extractionLoading: false, pdfUrl: 'invoice.pdf', pdfLoading: false,
  sourceTab: 'pdf', dataTab: 'extraction', emptyMessage: null,
  canRetry: false, onRetrySelected: () => {}, retrying: false, metricsLoading: false,
  onNavigate: () => {}, onSourceTab: () => {}, onDataTab: () => {}, totalDuration: '2 s', totalCost: '$0.0040',
  erpRows: [{ label: 'Pedido ERP', value: 'ERP-123' }],
  featureAmounts: { taxBase: '100 €', vatRate: '21%', vatAmount: '21 €', total: '121 €', lineItems: [],
    canExpandLineItems: false, lineItemsExpanded: false, onToggleLineItems: () => {} },
  extractionLabels: { ...es.extraction, verifactuLink: es.extraction.verifactuCheck, inferred: es.extraction.identifierTrace },
  identifierTrace: { supplier_nif: null, iban: null },
  labels: { ...es.invoices, decisionLabel: 'Escalar', count: '', erp: es.erp.title, erpData: es.erp.dataTitle,
    totalCost: es.invoices.processingCost, waiting: es.processing.waiting, appName: es.app.name,
    invoiceUnavailable: es.invoices.unavailable, notFound: es.invoices.pageNotFound, usage: es.usage.title },
}

describe('split invoice details', () => {
  test('hides absent QR metadata and links detected test codes without claiming verification', () => {
    expect(renderToStaticMarkup(<InvoiceDetails {...props} />)).not.toContain('QR Veri*Factu');
    const url = 'https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?nif=B12959755';
    const markup = renderToStaticMarkup(<InvoiceDetails {...props}
      selected={{ ...invoice, verifactu: { url, page: 1, environment: 'test' } }}
      extractionLabels={{ ...props.extractionLabels, verifactuLink: es.extraction.verifactuTest }} />)
    expect(markup).toContain(`href="${url}"`)
    expect(markup).toContain('rel="noopener noreferrer"')
    expect(markup).toContain(es.extraction.verifactuTest)
    expect(markup).not.toContain('Factura verificada')
  })
  test('marks only the inferred field without a separate trace block', () => {
    const entry = { label: es.extraction.identifierCorrection, characters: [{ value: '6', changed: true }] }
    const markup = renderToStaticMarkup(<InvoiceDetails {...props} identifierTrace={{ supplier_nif: entry, iban: null }} />)
    expect(markup).toContain(`aria-label="${es.extraction.identifierTrace}: B12345678"`)
    expect(markup.match(/lucide-circle-alert/g)).toHaveLength(1)
    expect(markup).not.toContain(entry.label)
    expect(markup).toContain('Revisar importe')
  })
  test('puts the document and source toggles on the left and metrics on the right', () => {
    const markup = renderToStaticMarkup(<InvoiceDetails {...props} />)
    const split = markup.indexOf('invoice-result-pane')
    const left = markup.slice(0, split)
    const right = markup.slice(split)
    expect(left).toContain('href="/invoices"')
    expect(left).toContain('factura.pdf')
    expect(left).toContain('data-pdf="invoice.pdf"')
    expect(right).toContain('$0.0040')
    expect(right).toContain('2 s')
    expect(right).toContain('Proveedor extraído')
    expect(right).toContain('Revisar importe')
    expect(left).not.toContain('Proveedor extraído')
  })

  test('source and data selections support all four independent combinations', () => {
    for (const sourceTab of ['pdf', 'text'] as const) {
      for (const dataTab of ['extraction', 'erp'] as const) {
        const markup = renderToStaticMarkup(<InvoiceDetails {...props} sourceTab={sourceTab} dataTab={dataTab} />)
        expect(markup.includes('Texto original de la factura')).toBe(sourceTab === 'text')
        expect(markup.includes('class="source-body" hidden=""')).toBe(sourceTab === 'text')
        expect(markup).toContain('Proveedor extraído')
        expect(markup.includes('ERP-123')).toBe(dataTab === 'erp')
        expect(markup.includes('invoice-processing-summary')).toBe(dataTab === 'extraction')
      }
    }
  })

  test('keeps both pane headers and skeletons while document data loads', () => {
    const markup = renderToStaticMarkup(<InvoiceDetails {...props} selected={null} invoiceName={null}
      pdfUrl={null} loading pdfLoading extractionLoading metricsLoading />)
    expect(markup.match(/class="invoice-pane-header"/g)).toHaveLength(2)
    expect(markup).toContain('invoice-pdf-skeleton')
    expect(markup).toContain('data-slot="skeleton"')
    expect(markup).not.toContain('$0.0040')
    for (const field of ['invoiceNumber', 'invoiceDate', 'purchaseOrder', 'supplierNif', 'iban', 'taxBase', 'vatRate', 'vatAmount', 'total', 'lineItems'] as const) {
      expect(markup).toContain(`<dt>${props.extractionLabels[field]}</dt>`)
    }
    expect(markup).not.toMatch(/<dt><div[^>]*data-slot="skeleton"/)
  })

  test('shows category icons beside extracted concepts, including Otros for unmatched lines', () => {
    const featureAmounts: NonNullable<Props['featureAmounts']> = {
      ...props.featureAmounts!,
      lineItems: [
        { description: 'Mantenimiento trimestral (1 ud)', amount: '100 €',
          category: { icon: maintenanceIcon, label: es.extraction.categories.maintenance } },
        { description: 'Ajuste por redondeo', amount: '-0,01 €',
          category: { icon: otherIcon, label: es.extraction.categories.other } },
      ],
    }
    const markup = renderToStaticMarkup(<InvoiceDetails {...props} featureAmounts={featureAmounts} />)
    expect(markup).toContain(`src="${maintenanceIcon}"`)
    expect(markup).toContain(`alt="${es.extraction.categories.maintenance}"`)
    expect(markup).toContain(`src="${otherIcon}"`)
    expect(markup).toContain(`alt="${es.extraction.categories.other}"`)
    expect(markup).toContain('width="24" height="24"')
    expect(markup.match(/class="extraction-category-icon"/g)).toHaveLength(2)
    expect(markup).toContain('Mantenimiento trimestral (1 ud)</span></span><span>100 €')
    expect(markup).toContain('Ajuste por redondeo</span></span><span>-0,01 €')
    const erpMarkup = renderToStaticMarkup(<InvoiceDetails {...props} featureAmounts={featureAmounts} dataTab="erp" />)
    expect(erpMarkup).not.toContain('extraction-category-icon')
    const loadingMarkup = renderToStaticMarkup(<InvoiceDetails {...props} featureAmounts={featureAmounts} extractionLoading />)
    expect(loadingMarkup).not.toContain('extraction-category-icon')
    expect(loadingMarkup).toContain('data-slot="skeleton"')
  })
})
