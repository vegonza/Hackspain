import { describe, expect, test } from 'bun:test'
import { useState } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createInstance } from 'i18next'
import { I18nextProvider } from 'react-i18next'
import { useInvoiceImports, type InvoiceUpload } from '../src/hooks/useInvoiceImports'
import { useInvoiceTable } from '../src/hooks/useInvoiceTable'
import { InvoiceImportPanel } from '../src/components/invoices/InvoiceImportPanel'
import { InvoicesTable } from '../src/components/invoices/InvoicesTable'
import type { Invoice } from '../src/api/invoices'
import es from '../src/locales/es/translation.json'

const i18n = createInstance()
await i18n.init({ lng: 'es', resources: { es: { translation: es } } })
const pending: Invoice = {
  id: 'new', name: 'new.pdf', sha256: 'hash', created_at: '2026-09-20T10:00:00Z', finished_at: null,
  status: 'processing', billing: null, last_error: null, next_retry_at: null, payment_decision: null,
  pages: 1, retry_attempts: 0, total_cost_usd: null, total_duration_ms: null,
}
const completed: Invoice = {
  ...pending, status: 'ready',
  billing: { invoice_number: 'FA-1', supplier_name: 'Proveedor', supplier_nif: 'B12345678', invoice_date: '2024-01-12',
    purchase_order: 'PO-1', line_items: [], currency: 'EUR', tax_base: '100', total: '121', tax_base_eur: '100', total_eur: '121' },
}
const upload: InvoiceUpload = { id: 'upload-1', name: 'local.pdf', status: 'uploading', file: new File(['pdf'], 'local.pdf') }

type Scenario = 'active' | 'completed' | 'error' | 'replacement' | 'new-batch' | 'deleted' | 'dismissed' | 'dismiss-active' | 'dismiss-error' | 'reopened'
function Lifecycle({ scenario }: { scenario: Scenario }) {
  const [step, setStep] = useState(0)
  const done = ['completed', 'new-batch', 'dismissed', 'reopened'].includes(scenario) && step > 0
  const invoices = [
    ...(scenario === 'replacement' ? step === 0 ? [] : [completed]
      : scenario === 'deleted' && step > 0 ? []
        : [(scenario === 'error' || scenario === 'dismiss-error') ? { ...pending, status: 'error' as const } : done ? completed : pending]),
    { ...completed, id: 'old', name: 'old.pdf', billing: { ...completed.billing!, invoice_date: '2025-01-12' } },
    ...((scenario === 'new-batch' || scenario === 'reopened') && step > 1 ? [{ ...pending, id: 'second', name: 'second.pdf' }] : []),
  ]
  const imports = useInvoiceImports(invoices, scenario === 'replacement' && step === 0 ? [upload] : [], true)
  const table = useInvoiceTable(invoices, false)
  if (step === 0) {
    table.onPeriod('2025-01')
    if (scenario === 'replacement') imports.track(completed.id)
    setStep(1)
  } else if (step === 1 && ['new-batch', 'dismissed', 'dismiss-active', 'dismiss-error', 'reopened'].includes(scenario)) {
    if (scenario !== 'new-batch') imports.onDismiss()
    setStep(2)
  }
  return <div data-period={table.period}>
    <InvoicesTable table={table} invoicesLoading={false} onUpload={async () => {}} onSelect={() => {}}
      onInvoiceLink={() => {}} onDelete={async () => {}} onRedo={async () => {}} deleting={false} redoDisabled={false} />
    <InvoiceImportPanel {...imports} onInvoiceLink={() => {}} onRetry={async () => {}} retryDisabled={false} />
  </div>
}
function StaticPanel({ invoices = [], uploads = [], isInvoiceList = true }: { invoices?: Invoice[]; uploads?: InvoiceUpload[]; isInvoiceList?: boolean }) {
  const imports = useInvoiceImports(invoices, uploads, isInvoiceList)
  return <InvoiceImportPanel {...imports} onInvoiceLink={() => {}} onRetry={async () => {}} retryDisabled={false} />
}
function render(scenario: Scenario): string {
  return renderToStaticMarkup(<I18nextProvider i18n={i18n}><Lifecycle scenario={scenario} /></I18nextProvider>)
}
function renderStatic(props: Parameters<typeof StaticPanel>[0]): string {
  return renderToStaticMarkup(<I18nextProvider i18n={i18n}><StaticPanel {...props} /></I18nextProvider>)
}

describe('invoice import panel', () => {
  test('stays hidden when no import needs tracking', () => {
    expect(renderStatic({ invoices: [completed] })).toBe('')
  })
  test('shows processing across months while keeping the selected month and its invoices visible', () => {
    const markup = render('active')
    expect(markup).toContain('data-period="2025-01"')
    expect(markup).toContain('old.pdf')
    expect(markup).toContain('href="/invoices/new"')
    expect(markup).toContain('0/1 facturas completas')
    expect(markup).toContain('value="0" max="1"')
    expect(markup).not.toContain('sidebar-processing')
    expect(markup.slice(markup.indexOf('<header class="invoice-import-header">'), markup.lastIndexOf('</header>'))).not.toContain('<svg')
    expect(markup).not.toContain('invoice-import-file-icon')
    expect(markup).not.toContain('class="invoice-import-status"')
    expect(markup).toMatch(/invoice-table-status" data-status="processing"><svg[^>]*upload-spinner/)
  })
  test('counts completion only after processing and retains links for invoices from other months', () => {
    const markup = render('completed')
    expect(markup).toContain('data-period="2025-01"')
    expect(markup).toContain('1/1 facturas completas')
    expect(markup).toContain('href="/invoices/new"')
    expect(markup).toContain('value="1" max="1"')
    expect(markup).toContain('aria-label="Cerrar"')
  })
  test('keeps failed uploads available to retry without a broken invoice link', () => {
    const markup = renderStatic({ uploads: [{ ...upload, status: 'error' }] })
    expect(markup).toContain('local.pdf')
    expect(markup).toContain('0/1 facturas completas')
    expect(markup).toContain('aria-label="Reintentar"')
    expect(markup).not.toContain('href=')
    expect(markup).toContain('aria-label="Cerrar"')
  })
  test('shows pending transfers separately from active uploads and processing failures', () => {
    const markup = renderStatic({ uploads: [upload, { ...upload, id: 'queued', status: 'queued' }], invoices: [{ ...pending, status: 'error' }] })
    expect(markup).toContain('Subiendo')
    expect(markup).toContain('En cola')
    expect(markup).toContain('0/3 facturas completas')
    expect(markup).toContain('aria-label="Reprocesar"')
  })
  test.each(['active', 'completed', 'error'] as const)('keeps the panel expanded and offers closing only after completion: %s', scenario => {
    const markup = render(scenario)
    expect(markup).toContain('invoice-import-panel')
    expect(markup).toContain('new.pdf')
    expect(markup).toContain('class="invoice-import-list"')
    expect(markup).not.toContain('invoice-import-toggle')
    expect(markup.includes('aria-label="Cerrar"')).toBe(scenario !== 'active')
  })
  test('replaces a local upload with the returned invoice even when it is already ready', () => {
    const markup = render('replacement')
    expect(markup).toContain('1/1 facturas completas')
    expect(markup).toContain('href="/invoices/new"')
    expect(markup).not.toContain('local.pdf')
  })
  test('keeps completed files when more work arrives', () => {
    const markup = render('new-batch')
    expect(markup).toContain('1/2 facturas completas')
    expect(markup).toContain('new.pdf')
    expect(markup).toContain('second.pdf')
  })
  test('hides outside the invoice list even while processing', () => {
    expect(renderStatic({ invoices: [pending], isInvoiceList: false })).toBe('')
  })
  test.each(['dismissed', 'dismiss-error'] as const)('dismisses finished imports: %s', scenario => {
    expect(render(scenario)).not.toContain('invoice-import-panel')
  })
  test('does not dismiss ongoing work', () => {
    expect(render('dismiss-active')).toContain('invoice-import-panel')
  })
  test('opens again when new work arrives after dismissal', () => {
    const markup = render('reopened')
    expect(markup).toContain('invoice-import-panel')
    expect(markup).toContain('second.pdf')
    expect(markup).not.toContain('aria-label="Cerrar"')
  })
  test('removes deleted invoices from the panel', () => {
    expect(render('deleted')).not.toContain('invoice-import-panel')
  })
})
