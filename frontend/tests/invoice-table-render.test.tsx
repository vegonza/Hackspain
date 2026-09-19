import { describe, expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { createInstance } from 'i18next'
import { I18nextProvider } from 'react-i18next'
import { InvoicesTableContainer } from '../src/components/invoices/InvoicesTableContainer'
import type { Invoice } from '../src/api/invoices'
import es from '../src/locales/es/translation.json'

const i18n = createInstance()
await i18n.init({ lng: 'es', resources: { es: { translation: es } } })

const invoices: Invoice[] = Array.from({ length: 500 }, (_, index) => ({
  id: `invoice-${index}`, name: `invoice-${index}.pdf`, sha256: 'hash',
  created_at: '2026-09-19T14:00:00Z', finished_at: null, status: 'ready', pages: 1, payment_decision: null,
  total_cost_usd: '0.004', total_duration_ms: 2000,
  retry_attempts: 0, last_error: null, next_retry_at: null,
}))

function render(rows: Invoice[], loading = false, search = ''): string {
  return renderToStaticMarkup(<I18nextProvider i18n={i18n}><InvoicesTableContainer
    rows={rows} invoicesLoading={loading} search={search} sortColumn={null} sortDirection="asc"
    onToggleSort={() => {}} onUpload={async () => {}} onSearch={() => {}} onSelect={() => {}}
    onInvoiceLink={() => {}} onDelete={async () => {}} onRedo={async () => {}} deleting={false} redoDisabled={false}
    labels={{ ...es.invoices, totalCost: es.usage.totalCost, errorStatus: es.invoices.errorStatus }}
  /></I18nextProvider>)
}

describe('document table rendering', () => {
  test('500 invoices render 50 rows with pagination before upload and preserve actions', () => {
    const markup = render(invoices)
    expect(markup.match(/class="[^"]*\binvoice-table-row\b/g)).toHaveLength(50)
    expect(markup).toContain('1–50 de 500')
    expect(markup).toContain('1 / 10')
    expect(markup.indexOf('aria-label="Paginación"')).toBeLessThan(markup.indexOf('upload-button'))
    expect(markup).toContain('href="/invoices/invoice-0"')
    expect(markup).toContain('aria-label="Reprocesar"')
    expect(markup).toContain('aria-label="Eliminar"')
    expect(markup).toContain('$0.0040')
    expect(markup).not.toContain('invoice-499.pdf')
  })

  test('newly visible rows use their document IDs and current status', () => {
    const markup = render([{ ...invoices[499], status: 'processing' }])
    expect(markup).toContain('href="/invoices/invoice-499"')
    expect(markup).toContain('Procesando')
    expect(markup).not.toContain('aria-label="Reprocesar"')
    expect(markup).not.toContain('aria-label="Eliminar"')
  })

  test('preserves loading skeletons and empty search results', () => {
    expect(render([], true)).toContain('data-slot="skeleton"')
    expect(render([], false, 'missing')).toContain(es.invoices.noResults)
    expect(render([])).toContain(es.invoices.emptyList)
  })
})
