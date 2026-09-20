import { describe, expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { createInstance } from 'i18next'
import { I18nextProvider } from 'react-i18next'
import { ClientsView } from '../src/components/clients/ClientsView'
import { useClients } from '../src/hooks/useClients'
import { parseRoute } from '../src/hooks/useAppRoute'
import es from '../src/locales/es/translation.json'

const i18n = createInstance()
await i18n.init({ lng: 'es', resources: { es: { translation: es } } })
function Harness({ loading }: { loading: boolean }) {
  const clients = useClients()
  return <ClientsView {...clients} loading={loading} rows={[{ id: 'client-1', name: 'Cliente visible', tax_id: 'B12345678', email: 'cliente@example.com', address: 'Calle Mayor 1', logo_url: '', deleteConfirmation: '¿Eliminar Cliente visible?' }]} />
}
describe('client directory', () => {
  test('clients have their own route outside invoice details', () => {
    expect(parseRoute('/clients')).toEqual({ view: 'clients', invoiceId: null })
  })
  test('shows searchable client details and the shared create/edit form entry points', () => {
    const html = renderToStaticMarkup(<I18nextProvider i18n={i18n}><Harness loading={false} /></I18nextProvider>)
    for (const value of ['Buscar clientes', 'Nuevo cliente', 'Acciones: Cliente visible', 'B12345678', 'cliente@example.com', 'Calle Mayor 1']) expect(html).toContain(value)
    expect(html).not.toContain('aria-label="Paginación"')
    expect(html).toContain('lucide-ellipsis')
    expect(html).not.toContain('lucide-pencil')
    expect(html).toContain('data-openable="false"')
    expect(html).toContain('left-0 z-30')
    expect(html).toContain('invoice-table-action')
  })
  test('loading fills the table without exposing rows', () => {
    const html = renderToStaticMarkup(<I18nextProvider i18n={i18n}><Harness loading /></I18nextProvider>)
    const rows = [...html.matchAll(/<tr[^>]*aria-hidden="true"[\s\S]*?<\/tr>/g)]
    expect(rows).toHaveLength(50)
    for (const [row] of rows) expect(row.match(/<td\b/g)).toHaveLength(5)
    expect(html).not.toContain('Cliente visible')
  })
})
