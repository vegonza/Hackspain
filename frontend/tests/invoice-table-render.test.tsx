import { describe, expect, test } from 'bun:test'
import { useState } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createInstance } from 'i18next'
import { I18nextProvider } from 'react-i18next'
import { InvoicesTable } from '../src/components/invoices/InvoicesTable'
import { useInvoiceTable } from '../src/hooks/useInvoiceTable'
import { shiftMonth } from '../src/hooks/invoiceBilling'
import type { Invoice } from '../src/api/invoices'
import es from '../src/locales/es/translation.json'

const i18n = createInstance()
await i18n.init({ lng: 'es', resources: { es: { translation: es } } })
const now = new Date()
const invoiceDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-12`
const invoices: Invoice[] = Array.from({ length: 500 }, (_, index) => ({
  id: `invoice-${index}`, name: `invoice-${index}.pdf`, sha256: 'hash',
  created_at: '2026-09-19T14:00:00Z', finished_at: null, status: 'ready', pages: 1,
  payment_decision: { classification: 'PAGAR', reasons: [], checks: { not_paid: true } },
  total_cost_usd: '0.004', total_duration_ms: 2000,
  retry_attempts: 0, last_error: null, next_retry_at: null,
  billing: { invoice_number: `FA-${index}`, supplier_name: `Proveedor ${index}`, supplier_nif: 'B12345678',
    invoice_date: invoiceDate, purchase_order: 'PO-1', line_items: [{ description: 'Mantenimiento', amount: '100' }],
    currency: 'EUR', tax_base: '100', total: '121', tax_base_eur: '100', total_eur: '121' },
}))

function Harness({ rows, loading }: { rows: Invoice[]; loading: boolean }) {
  const table = useInvoiceTable(rows, loading)
  return <InvoicesTable table={table} invoicesLoading={loading} onUpload={async () => {}} onSelect={() => {}}
    onInvoiceLink={() => {}} onDelete={async () => {}} onRedo={async () => {}} deleting={false} redoDisabled={false} />
}
function render(rows: Invoice[], loading = false): string {
  return renderToStaticMarkup(<I18nextProvider i18n={i18n}><Harness rows={rows} loading={loading} /></I18nextProvider>)
}

describe('invoice billing table rendering', () => {
  test('limits month navigation and selection to the current month', () => {
    const currentMonth = invoiceDate.slice(0, 7)
    const futureMonth = shiftMonth(currentMonth, 1)
    const previousMonth = shiftMonth(currentMonth, -1)
    const futureInvoice = { ...invoices[0], billing: { ...invoices[0].billing!, invoice_date: `${futureMonth}-12` } }
    const monthInvoices = [futureInvoice, invoices[0], invoices[1],
      { ...invoices[2], billing: { ...invoices[2].billing!, invoice_date: `${previousMonth}-12` } },
      { ...invoices[3], billing: null }]
    const actions = ['next', 'previous', 'next', 'next', futureMonth, 'all', futureMonth, 'undated', 'next', currentMonth]
    const periods = [currentMonth, currentMonth, previousMonth, currentMonth, currentMonth, currentMonth, 'all', 'all', 'undated', 'undated', currentMonth]
    function NavigationHarness() {
      const [step, setStep] = useState(0)
      const table = useInvoiceTable(monthInvoices, false)
      expect(table.period).toBe(periods[step])
      expect(table.monthOptions.some(option => option.value === futureMonth)).toBe(false)
      expect(table.monthOptions.some(option => option.value === currentMonth)).toBe(true)
      expect(table.monthOptions.find(option => option.value === currentMonth)!.count).toBe(2)
      expect(table.monthOptions.find(option => option.value === previousMonth)!.count).toBe(1)
      expect(table.monthOptions.find(option => option.value === 'all')!.count).toBe(5)
      expect(table.monthOptions.find(option => option.value === 'undated')).toEqual({ value: 'undated', label: 'Sin fecha', count: 1 })
      expect(table.canNextMonth).toBe(table.period === previousMonth)
      if (step < actions.length) {
        const action = actions[step]
        if (action === 'next') table.onNextMonth()
        else if (action === 'previous') table.onPreviousMonth()
        else table.onPeriod(action)
        setStep(step + 1)
      }
      return null
    }
    renderToStaticMarkup(<I18nextProvider i18n={i18n}><NavigationHarness /></I18nextProvider>)
    expect(render([])).toMatch(/aria-label="Mes siguiente"[^>]*disabled=""/)
  })
  test.each([
    ['Consultoría Estratégica Ibérica S.L.', 'B87654321', 'consultoria-estrategica-iberica.svg'],
    ['Mensajería Rápida del Sur S.L.', 'B9263808', 'p011-mensajeria-rapida-del-sur.svg'],
    ['Catering Hermanos Pico S.L.', 'B98120774', 'p005-catering-hermanos-pico.svg'],
    ['Informática Benimámet S.L.', 'B98120774', 'p010-informatica-benimamet.svg'],
    ['Limpiezas Turia S.L.', 'B90233808', 'p004-limpiezas-turia.svg'],
  ])('shows the named supplier logo for %s independently of the extracted tax ID', (name, taxId, filename) => {
    const markup = render([{ ...invoices[0], billing: { ...invoices[0].billing!, supplier_name: name, supplier_nif: taxId } }])
    expect(markup).toContain(filename)
    expect(markup).toContain('class="billing-supplier-logo"')
    expect(markup).not.toContain('class="billing-avatar"')
    expect(markup).toContain(name)
  })

  test('renders all 500 invoices without pagination and retains business information and actions', () => {
    const markup = render(invoices)
    expect(markup.match(/class="[^"]*\binvoice-table-row\b/g)).toHaveLength(500)
    expect(markup).not.toContain('aria-label="Paginación"')
    expect(markup.indexOf('placeholder="Buscar proveedor, factura, pedido…"')).toBeLessThan(markup.indexOf('upload-button'))
    expect(markup.indexOf('upload-button')).toBeLessThan(markup.indexOf('class="billing-month"'))
    expect(markup).not.toContain('Descargar facturas')
    expect(markup).toContain('accept=".pdf,.doc,.docx,.odt,.rtf,.ppt,.pptx,.odp,.xls,.xlsx,.ods"')
    expect(markup).not.toContain('class="table-toolbar"')
    expect(markup).not.toContain('billing-filters')
    expect(markup).not.toContain('Todos los proveedores')
    expect(markup).toContain('Total con IVA')
    expect(markup).toContain('href="/invoices/invoice-0"')
    expect(markup.match(/aria-label="Acciones"/g)).toHaveLength(500)
    expect(markup).not.toContain('aria-label="Reprocesar"')
    expect(markup).not.toContain('aria-label="Eliminar"')
    expect(markup).toContain('Proveedor 0')
    expect(markup).toContain('Mantenimiento')
    expect(markup).toContain('FA-0 · invoice-0.pdf · Mantenimiento')
    expect(markup).toContain('121,00')
    expect(markup).toMatch(/<strong>100,00[^<]*<\/strong><span>Con IVA 121,00/)
    expect(markup).not.toContain('$0.0040')
    expect(markup).not.toContain('Fecha de subida')
    expect(markup).not.toContain('Completado')
    expect(markup).toContain('href="/invoices/invoice-499"')
  })
  test('processing rows show a single actions menu instead of individual action icons', () => {
    const markup = render([{ ...invoices[499], status: 'processing' }])
    expect(markup).toContain('href="/invoices/invoice-499"')
    expect(markup).toContain('Procesando')
    expect(markup).toContain('aria-label="Acciones"')
    expect(markup).toContain('aria-haspopup="menu"')
    expect(markup).not.toContain('aria-label="Reprocesar"')
    expect(markup).not.toContain('aria-label="Eliminar"')
    expect(markup).not.toContain('aria-label="Descargar PDF"')
  })
  test('renders a full table of skeletons and no pagination for small lists', () => {
    expect(render([], true).match(/class="[^"]*\binvoice-table-row\b/g)).toHaveLength(50)
    expect(render([])).toContain(es.invoices.emptyList)
    expect(render(invoices.slice(0, 15))).not.toContain('aria-label="Paginación"')
  })
  test('keeps undated files accessible without placing them in their upload month', () => {
    const markup = render([{ ...invoices[0], billing: null }])
    expect(markup).toContain('aria-label="Mes de facturación"')
    expect(markup).toContain(es.billing.empty)
  })
  test('retains original-currency amounts when no EUR conversion is stored', () => {
    const markup = render([{ ...invoices[0], billing: { ...invoices[0].billing!, currency: 'MXN', tax_base: '100', total: '121', tax_base_eur: null, total_eur: null } }])
    expect(markup).toContain('121,00')
    expect(markup).toMatch(/<strong><span class="billing-currency-info"[^>]*>.*?<\/span>100,00[^<]*<\/strong><span>Con IVA 121,00/)
    expect(markup).toContain('MXN')
    expect(markup).toContain('billing-incomplete')
  })
  test('approved rows do not repeat verification boilerplate', () => {
    const markup = render([{ ...invoices[0], payment_decision: { classification: 'PAGAR', reasons: ['Identidad, pedido, ERP, importes y fecha verificados.'], checks: { not_paid: true } } }])
    expect(markup).not.toContain('Identidad, pedido, ERP, importes y fecha verificados.')
    expect(markup).toContain('Lista para pagar')
    expect(markup).toContain('aria-label="Acciones"')
  })
  test('review rows keep reasons out of the row and use padded dates', () => {
    const markup = render([{ ...invoices[0], payment_decision: { classification: 'ESCALAR', reasons: ['El IBAN no coincide.', 'Revisar el pedido.'], checks: { not_paid: true } } }])
    expect(markup).not.toContain('El IBAN no coincide.')
    expect(markup).not.toContain('Revisar el pedido.')
    expect(markup).toContain(`12/${String(now.getMonth() + 1).padStart(2, '0')}/${now.getFullYear()}`)
  })
  test('missing net amounts do not substitute the gross amount', () => {
    const markup = render([{ ...invoices[0], billing: { ...invoices[0].billing!, tax_base: null, tax_base_eur: null } }])
    expect(markup).toMatch(/<strong>—<\/strong><span>Con IVA 121,00/)
  })
  test('converted invoices show an original-amount tooltip icon without a third price line', () => {
    const markup = render([{ ...invoices[0], billing: { ...invoices[0].billing!, currency: 'USD', tax_base: '100', total: '121', tax_base_eur: '92', total_eur: '111.32' } }])
    expect(markup).toMatch(/<strong><span class="billing-currency-info"[^>]*>.*?<\/span>92,00[^<]*<\/strong><span>Con IVA 111,32/)
    expect(markup).toContain('aria-label="Original 100,00')
    expect(markup).toContain('sin IVA')
    expect(markup.replace(/<[^>]+>/g, '')).not.toContain('Original 100,00')
    expect(markup).toContain('</strong><span>Con IVA 111,32')
  })
  test('does not label an ERP-paid invoice as ready to pay', () => {
    const markup = render([{ ...invoices[0], payment_decision: { classification: 'NO_PAGAR', reasons: ['Ya pagada'], checks: { not_paid: false } } }])
    expect(markup).toContain('Pagada en ERP')
    expect(markup).not.toContain('data-decision="PAGAR"')
  })
})
