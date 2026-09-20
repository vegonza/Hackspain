import { describe, expect, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { createInstance } from 'i18next'
import { I18nextProvider } from 'react-i18next'
import { AnalyticsView } from '../src/components/analytics/AnalyticsView'
import { useAnalytics } from '../src/hooks/useAnalytics'
import es from '../src/locales/es/translation.json'

const i18n = createInstance()
await i18n.init({ lng: 'es', resources: { es: { translation: es } } })

function Harness({ loading }: { loading: boolean }) {
  const analytics = useAnalytics()
  return <AnalyticsView {...analytics} loading={loading} averageDurationLabel="3 s" cadenceLabel="0,3 s/factura"
    supplierTotalLabel="121,00 €" supplierItems={[
      { id: 'B12345678', label: 'Proveedor de prueba', amount: 121, amountLabel: '121,00 €',
        percentageLabel: '100,0 %', color: '#2f6b5f', icon: null },
    ]} />
}

const render = (loading: boolean) => renderToStaticMarkup(<I18nextProvider i18n={i18n}><Harness loading={loading} /></I18nextProvider>)

describe('analytics layout', () => {
  test('keeps four chart cards and places both timing metrics inside the cost chart', () => {
    const markup = render(false)
    expect(markup.match(/class="analytics-card(?: |")/g)).toHaveLength(4)
    expect(markup).toContain(es.analytics.spendingDistribution)
    expect(markup).toContain(es.analytics.supplierDistribution)
    const costChart = markup.slice(markup.indexOf('analytics-usage-card'), markup.indexOf(es.analytics.supplierDistribution))
    expect(costChart).toContain('analytics-usage-sidebar')
    expect(costChart).toContain(es.analytics.averageDuration)
    expect(costChart).toContain(es.analytics.estimatedCadence)
    expect(costChart).toContain('3 s')
    expect(costChart).toContain('0,3 s/factura')
    expect(markup).toContain('Proveedor de prueba')
    expect(markup).toContain('100,0 %')
  })

  test('retains chart titles and metric labels while only values and charts load', () => {
    const markup = render(true)
    expect(markup).toContain(es.analytics.supplierDistribution)
    expect(markup).toContain(es.analytics.averageDuration)
    expect(markup).toContain(es.analytics.estimatedCadence)
    expect(markup).toContain('data-slot="skeleton"')
    expect(markup).not.toContain('Proveedor de prueba')
    expect(markup).not.toContain('0,3 s/factura')
  })
})
