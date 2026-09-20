import { afterEach, describe, expect, spyOn, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { fetchGestoria, saveGestoria, sendGestoria } from '../src/api/gestoria'
import { Dialog } from '../src/components/ui/dialog'
import { GestoriaMenu } from '../src/components/gestoria/GestoriaMenu'
import { gestoriaStatusBadge } from '../src/hooks/gestoriaStatuses'
import i18n from '../src/i18n'
import { useGestoria } from '../src/hooks/useGestoria'
import { i18nInitialized } from '../src/i18n'
import es from '../src/locales/es/translation.json'

await i18nInitialized
const requests: ReturnType<typeof spyOn>[] = []
afterEach(() => { requests.forEach(mock => mock.mockRestore()); requests.length = 0 })

describe('Gestoría', () => {
  test('saves the email through the centralized API and accepts an empty 204 response', async () => {
    const fetch = spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }))
    requests.push(fetch)
    await saveGestoria('gestoria@example.com')
    expect(fetch.mock.calls[0]).toEqual(['/api/gestoria', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: '{"email":"gestoria@example.com"}' }])
  })
  test('loads sendable unsent candidates for the selected month', async () => {
    const overview = { email: 'gestoria@example.com', invoices: [{ id: 'received', name: 'invoice.pdf', kind: 'received' }], statuses: [] }
    const fetch = spyOn(globalThis, 'fetch').mockResolvedValue(Response.json(overview))
    requests.push(fetch)
    const signal = new AbortController().signal
    expect(await fetchGestoria('2026-08', signal)).toEqual(overview)
    expect(fetch.mock.calls[0]).toEqual(['/api/gestoria?period=2026-08', { signal }])
  })
  test('sends the reviewed received and issued IDs in the request body', async () => {
    const fetch = spyOn(globalThis, 'fetch').mockResolvedValue(Response.json({ sent: 2 }))
    requests.push(fetch)
    expect(await sendGestoria('gestoria@example.com', [{ id: 'received', name: 'A.pdf', kind: 'received' }, { id: 'issued', name: 'B.pdf', kind: 'issued' }], '2026-08')).toEqual({ sent: 2 })
    expect(fetch.mock.calls[0][0]).toBe('/api/gestoria/send')
    expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({ email: 'gestoria@example.com', period: '2026-08', received_ids: ['received'], issued_ids: ['issued'] })
  })
  test('uses the shared dialog, retains labels during loading and disables sending until loaded', () => {
    function Harness() {
      const gestoria = useGestoria('2026-08', 'Agosto de 2026')
      const menu = GestoriaMenu({ gestoria })
      const content = menu.props.children
      expect(content.props.closeLabel).toBe(es.common.close)
      expect(content.props['aria-describedby']).toBe('gestoria-period')
      return <Dialog>{content.props.children}</Dialog>
    }
    const markup = renderToStaticMarkup(<Harness />)
    expect(markup).toContain('Agosto de 2026')
    expect(markup).toContain(es.gestoria.ready)
    expect(markup).not.toContain('data-slot="badge"')
    expect(markup).not.toContain('<p')
    expect(markup).toContain(es.gestoria.email)
    expect(markup).toContain(es.common.cancel)
    expect(markup).toMatch(/type="submit" disabled=""/)
    expect(markup).toContain('data-slot="skeleton"')
  })
  test('shows only sendable status badges with counts under Listo para enviar', () => {
    function Harness() {
      const gestoria = useGestoria('2026-08', 'Agosto de 2026')
      const statuses = [
        { kind: 'received' as const, status: 'PAGAR' as const, count: 5 },
        { kind: 'issued' as const, status: 'paid' as const, count: 1 },
      ].map(row => ({ key: `${row.kind}-${row.status}`, count: row.count, badge: gestoriaStatusBadge(row, i18n.t) }))
      const menu = GestoriaMenu({ gestoria: { ...gestoria, loading: false, statuses } })
      return <Dialog>{menu.props.children.props.children}</Dialog>
    }
    const markup = renderToStaticMarkup(<Harness />)
    expect(markup).toContain(es.billing.rowDecisions.PAGAR)
    expect(markup).toContain('data-decision="PAGAR"')
    expect(markup).not.toContain(es.billing.rowDecisions.NO_PAGAR)
    expect(markup).not.toContain(es.billing.rowDecisions.ESCALAR)
    expect(markup).toContain(es.issued.status.paid)
    expect(markup).toContain('data-tone="success"')
    expect(markup.match(/data-slot="badge"/g)).toHaveLength(2)
    expect(markup).toContain('class="tabular-nums">5</span>')
    expect(markup).not.toContain('Recibidas')
    expect(markup).not.toContain('Emitidas')
  })

})
