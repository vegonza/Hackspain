import { useGestoria } from '../src/hooks/useGestoria'
import { describe, expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { createInstance } from 'i18next'
import { I18nextProvider } from 'react-i18next'
import { IssuedInvoiceEditor } from '../src/components/issued/IssuedInvoiceEditor'
import { useIssuedEditor } from '../src/hooks/useIssuedEditor'
import { InvoicesTable } from '../src/components/invoices/InvoicesTable'
import { useIssuedInvoices } from '../src/hooks/useIssuedInvoices'
import { issuedTotals } from '../src/hooks/issuedAmounts'
import { useInvoiceTable } from '../src/hooks/useInvoiceTable'
import { useIssuedList } from '../src/hooks/useIssuedList'
import { formatDateShort } from '../src/lib/format'
import { supplierLogo } from '../src/lib/supplierLogos'
import bancoMiralmar from '../src/assets/banco-miralmar.svg'
import templateQr from '../src/assets/invoice-template-qr.svg'
import { parseRoute } from '../src/hooks/useAppRoute'
import type { IssuedInvoice } from '../src/api/issued'
import type { BillingInvoice } from '../src/hooks/invoiceBilling'
import es from '../src/locales/es/translation.json'

const i18n = createInstance()
await i18n.init({ lng: 'es', resources: { es: { translation: es } } })
const now = new Date()
const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const invoice: IssuedInvoice = {
  id: 'issued-1', client_id: 'client-1', status: 'issued', invoice_number: 'F-2026-0001',
  issue_date: `${month}-01`, due_date: `${month}-28`, notes: '',
  company: { name: 'Banco Miralmar S.A.', tax_id: 'A58231074', address: 'Paseo de la Castellana 214, Madrid', email: '', logo_url: '', iban: '', payment_method: '' }, client: { name: 'Cliente Único', tax_id: 'B12345678', address: 'Madrid', email: '', logo_url: '' },
  items: [{ description: 'Consultoría', quantity: '1', unit_price: '100', tax_rate: '21' }],
  base_amount: '100', tax_amount: '21', total_amount: '121', pdf_path: 'issued/example.pdf', created_at: '2026-09-20T10:00:00Z', paid_at: null, verifactu_test: null,
}
const received: BillingInvoice = {
  id: 'received-1', name: 'received.pdf', status: 'ready', created_at: '2026-09-20T10:00:00Z', payment_decision: null, last_error: null, next_retry_at: null,
  billing: { invoice_number: 'EXP-1', supplier_name: 'Proveedor', supplier_nif: 'B1234', invoice_date: `${month}-01`, purchase_order: null, line_items: [], currency: 'EUR', tax_base: '20', tax_base_eur: '20', total: '24.2', total_eur: '24.2' },
}

function TableHarness({ state }: { state: 'ready' | 'loading' | 'empty' | 'error' }) {
  const issued = useIssuedInvoices()
  const issuedRows = state === 'empty' ? [] : [invoice]
  const table = useInvoiceTable(state === 'empty' ? [] : [received], state === 'loading', issuedRows)
  const list = useIssuedList(issuedRows, table.period, table.search, table.sort)
  return <InvoicesTable gestoria={useGestoria(table.period, table.monthOptions.find(option => option.value === table.period)!.label)} table={table} issued={{ ...issued, loading: state === 'loading', failed: state === 'error' }} issuedList={list}
    invoicesLoading={state === 'loading'} onUpload={async () => {}} onSelect={() => {}} onInvoiceLink={() => {}}
    onDelete={async () => {}} onRedo={async () => {}} deleting={false} redoDisabled={false} />
}

describe('issued invoice billing', () => {
  test('new invoices expose issuance without a save-draft action and use the issuer identity', () => {
    function EditorHarness() {
      const editor = useIssuedEditor('new', () => {})
      return <IssuedInvoiceEditor editor={{ ...editor, loading: false, company: invoice.company, companyLogo: supplierLogo(invoice.company.name), client: invoice.client }} />
    }
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><EditorHarness /></I18nextProvider>)
    expect(markup).toContain('Emitir factura')
    expect(markup.toLocaleLowerCase('es')).not.toContain('borrador')
    expect(markup).toContain(`src="${templateQr}"`)
    expect(markup).toContain('alt="Plantilla"')
    expect(markup).toContain('QR tributario')
    expect(markup).toContain('VERI*FACTU')
    expect(markup).not.toContain('hUMAnos')
    expect(markup).toContain('Banco Miralmar S.A.')
    expect(markup.split(`src="${bancoMiralmar}"`)).toHaveLength(2)
    expect(markup).not.toContain('class="issued-company-logo"')
    const form = markup.match(/<form\b[\s\S]*?<\/form>/)![0]
    expect(form).not.toContain(es.issued.company)
    expect(markup).toContain('class="issued-preview-logo"')
    expect(markup).toContain('A58231074')
    expect(markup).toContain('Paseo de la Castellana 214, Madrid')
    expect(markup).not.toContain(es.issued.paymentInfo)
  })

  test.each([null, 'TEST-CSV'])('issued QR with receipt %s stays separate from registration', csv => {
    const receipt = { parties: null, qr_code: 'data:image/bmp;base64,real-provider-qr', csv, submitted_at: csv === null ? null : '2026-09-20T10:00:00Z', pdf_path: invoice.pdf_path }
    function EditorHarness() {
      const editor = useIssuedEditor(invoice.id, () => {})
      return <IssuedInvoiceEditor editor={{ ...editor, loading: false, valuesLoading: false, locked: true,
        invoice: { ...invoice, verifactu_test: receipt }, canSubmitVerifactu: csv === null, showQr: true,
        previewQr: csv === null ? null : receipt.qr_code, previewQrAlt: es.issued.verifactuQr }} />
    }
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><EditorHarness /></I18nextProvider>)
    expect(markup).not.toContain(`src="${templateQr}"`)
    expect(markup).not.toContain('alt="Plantilla"')
    expect(markup.match(/>Descargar PDF<\/button>/g)).toHaveLength(1)
    expect(markup).not.toContain('PDF Veri*Factu test')
    if (csv === null) {
      expect(markup).not.toContain(`src="${receipt.qr_code}"`)
      expect(markup).toContain(es.issued.qrPending)
      expect(markup).toContain(es.issued.verifactu)
    } else {
      expect(markup).toContain(`src="${receipt.qr_code}"`)
      expect(markup).not.toContain(es.issued.verifactu)
    }
  })

  test.each(['new', 'issued-1'])('loading %s preserves the editor controls and invoice headings', id => {
    function EditorHarness() {
      const editor = useIssuedEditor(id, () => {})
      return <IssuedInvoiceEditor editor={editor} />
    }
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><EditorHarness /></I18nextProvider>)
    for (const label of [es.issued.client, es.issued.issueDate, es.issued.dueDate, es.issued.description,
      es.issued.quantity, es.issued.unitPrice, es.issued.taxRate, es.issued.notes, es.issued.addLine,
      es.issued.base, es.issued.tax, es.issued.total, es.issued.company, es.issued.concepts,
      es.issued.verifactuQr, es.issued.verifactuLabel, es.issued.thanks]) expect(markup).toContain(label)
    expect(markup).toContain('<fieldset disabled=""')
    expect(markup).toContain('role="combobox"')
    expect(markup).toContain('type="date"')
    expect(markup).toContain('<textarea')
    expect(markup).not.toContain('h-[700px]')
    const header = markup.match(/<thead>[\s\S]*?<\/thead>/)![0]
    expect(header).not.toContain('data-slot="skeleton"')
    if (id === 'new') {
      expect(markup).toContain('Emitir factura')
      expect(markup).toContain(`src="${templateQr}"`)
    } else {
      expect(markup).not.toContain('Emitir factura')
      expect(markup).not.toContain('0,00')
      expect(markup).not.toContain(`src="${templateQr}"`)
    }
  })

  test.each(['ready', 'loading', 'empty'] as const)('received and issued tables share their layout in the %s state', state => {
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><TableHarness state={state} /></I18nextProvider>)
    const tables = [...markup.matchAll(/<table\b[\s\S]*?<\/table>/g)].map(match => match[0])
    expect(tables).toHaveLength(2)
    const classes = (table: string) => [...table.replace(/<tr[^>]*>[\s\S]*?<\/tr>/, '').matchAll(/class="([^"]*)"/g)].map(match => match[1])
    expect(classes(tables[0])).toEqual(classes(tables[1]))
    expect(tables[0].match(/<colgroup>[\s\S]*?<\/colgroup>/)![0]).toBe(tables[1].match(/<colgroup>[\s\S]*?<\/colgroup>/)![0])
    if (state === 'ready') {
      for (const table of tables) {
        expect(table).toContain('aria-label="Acciones"')
        expect(table).toContain('lucide-ellipsis')
        expect(table).not.toContain('lucide-download')
        expect(table).toContain(formatDateShort(`${month}-01T12:00:00`, 'es-ES'))
        expect(table).toContain('class="billing-secondary"')
      }
    }
    if (state === 'loading') for (const table of tables) {
      expect(table.match(/<tr[^>]*aria-hidden="true"/g)).toHaveLength(50)
      expect(table).toContain('billing-identity')
      expect(table).toContain('billing-money')
      expect(table).toContain('lucide-ellipsis')
      expect(table).toContain('Con IVA')
      expect(table.match(/<th[^>]*aria-sort[\s\S]*?<\/th>/)![0]).not.toContain('data-slot="skeleton"')
    }
    if (state === 'empty') for (const table of tables) expect(table).toContain('h-48 text-center text-muted-foreground')
  })
  test('each section title, tools and column labels occupy the same sticky table header', () => {
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><TableHarness state="ready" /></I18nextProvider>)
    const headers = [...markup.matchAll(/<thead\b[\s\S]*?<\/thead>/g)].map(match => match[0])
    expect(headers).toHaveLength(2)
    for (const [index, header] of headers.entries()) {
      expect(header).toContain('billing-section-sticky')
      expect(header).toContain(index === 0 ? es.issued.received : es.issued.section)
      expect(header).toContain(index === 0 ? es.billing.payable : es.issued.new)
      expect(header).toContain(es.billing.date)
      expect(header).toContain(es.billing.amount)
      expect(header.match(/<tr\b/g)).toHaveLength(2)
      expect(header.match(/aria-sort="none"/g)).toHaveLength(4)
    }
  })
  test('issued invoices support the incoming status sort and its unsorted state', () => {
    const issued = [{ ...invoice, id: 'z', status: 'issued' as const }, { ...invoice, id: 'a', status: 'issuing' as const }]
    function Harness() {
      const sorted = useIssuedList(issued, month, '', { column: 'review', direction: 'asc' })
      const original = useIssuedList(issued, month, '', { column: null, direction: 'asc' })
      expect(sorted.rows.map(row => row.id)).toEqual(['a', 'z'])
      expect(original.rows.map(row => row.id)).toEqual(['z', 'a'])
      return null
    }
    renderToStaticMarkup(<I18nextProvider i18n={i18n}><Harness /></I18nextProvider>)
  })
  test('failed invoice loading shows the error without a stray retry button or a false empty state', () => {
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><TableHarness state="error" /></I18nextProvider>)
    expect(markup).toContain(es.issued.failed)
    expect(markup).not.toContain('Reintentar')
    expect(markup).not.toContain(es.issued.empty)
  })
  test('rounds each line before summing mixed VAT rates', () => {
    const totals = issuedTotals([{ description: 'A', quantity: '3', unit_price: '0.335', tax_rate: '21' }, { description: 'B', quantity: '2', unit_price: '10', tax_rate: '10' }])
    expect(totals).toEqual({ lines: [{ base: 1.01, tax: 0.21 }, { base: 20, tax: 2 }], base: 21.01, tax: 2.21, total: 23.22 })
  })
  test('allows blank numeric input while editing without crashing the preview', () => {
    expect(issuedTotals([{ description: '', quantity: '', unit_price: '.', tax_rate: '' }]).total).toBe(0)
  })
  test('counts both invoice types in the month but only issued income in totals, using net expenses', () => {
    const issued = [invoice, { ...invoice, id: 'paid', status: 'paid' as const }, { ...invoice, id: 'issuing', status: 'issuing' as const }]
    function Harness() {
      const table = useInvoiceTable([received], false, issued)
      expect(table.issuedSummaries.map(row => row.cents)).toEqual([20000, 18000])
      expect(table.receivedSummaries[0].cents).toBe(2000)
      expect(table.monthOptions.find(option => option.value === month)!.count).toBe(4)
      expect(table.receivedSummaries).toHaveLength(3)
      return null
    }
    renderToStaticMarkup(<I18nextProvider i18n={i18n}><Harness /></I18nextProvider>)
  })
  test.each(['cliente unico', 'F-2026-0001', 'issued-1', 'consultoria'])('searches issued invoices by %s', search => {
    function Harness() {
      const list = useIssuedList([invoice], month, search, { column: 'date', direction: 'desc' })
      expect(list.rows.map(row => row.id)).toEqual(['issued-1'])
      expect(list.rows[0].amount).toContain('100,00')
      expect(list.rows[0].gross).toContain('121,00')
      return null
    }
    renderToStaticMarkup(<I18nextProvider i18n={i18n}><Harness /></I18nextProvider>)
  })
  test('issued routes never enter the extraction detail route', () => {
    expect(parseRoute('/invoices/issued/new')).toEqual({ view: 'issued', invoiceId: null, issuedId: 'new' })
    expect(parseRoute('/invoices/issued/id')).toEqual({ view: 'issued', invoiceId: null, issuedId: 'id' })
    expect(parseRoute('/invoices/received')).toEqual({ view: 'invoices', invoiceId: 'received' })
  })
})
