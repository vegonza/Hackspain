import { describe, expect, test } from 'bun:test'
import { useState } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createInstance } from 'i18next'
import { I18nextProvider } from 'react-i18next'
import { TableToolbar } from '../src/components/ui/table-toolbar'
import { useTablePagination } from '../src/hooks/useTablePagination'
import es from '../src/locales/es/translation.json'

const i18n = createInstance()
await i18n.init({ lng: 'es', resources: { es: { translation: es } } })
const records = Array.from({ length: 501 }, (_, index) => `row-${index}`)

function TableHarness({ action = true, nextPage = false, filterAfter = false, count = 501 }: { action?: boolean; nextPage?: boolean; filterAfter?: boolean; count?: number }) {
  const [step, setStep] = useState(0)
  const filtered = filterAfter && step >= 2
  const table = useTablePagination(filtered ? records.slice(-1) : records.slice(0, count), filtered ? 'row-500' : '')
  if (step === 0 && nextPage) {
    table.pagination.onNext()
    setStep(1)
  } else if (step === 1 && filterAfter) {
    setStep(2)
  }
  return <>
    <TableToolbar pagination={table.pagination} loading={false} actions={action ? <button data-action="upload">Subir PDF</button> : undefined}>
      <span>Contenido</span>
    </TableToolbar>
    <ul>{table.rows.map(row => <li key={row}>{row}</li>)}</ul>
  </>
}

describe('shared table toolbar', () => {
  test('pagination and actions share one right-hand group in a fixed order', () => {
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><TableHarness /></I18nextProvider>)
    const content = markup.indexOf('table-toolbar-content')
    const controls = markup.indexOf('table-toolbar-controls')
    const pagination = markup.indexOf('aria-label="Paginación"')
    const action = markup.indexOf('data-action="upload"')
    expect(content).toBeLessThan(controls)
    expect(controls).toBeLessThan(pagination)
    expect(pagination).toBeLessThan(action)
    expect(markup).toContain('1–50 de 501')
    expect(markup.match(/<li>/g)).toHaveLength(50)
  })

  test('tables without actions use the same toolbar and controls group', () => {
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><TableHarness action={false} /></I18nextProvider>)
    expect(markup).toContain('class="table-toolbar"')
    expect(markup).toContain('class="table-toolbar-controls"')
    expect(markup).toContain('1–50 de 501')
    expect(markup).not.toContain('data-action="upload"')
  })

  test('next shows only the next 50 cached rows', () => {
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><TableHarness nextPage /></I18nextProvider>)
    expect(markup).toContain('51–100 de 501')
    expect(markup).toContain('<li>row-50</li>')
    expect(markup).toContain('<li>row-99</li>')
    expect(markup).not.toContain('<li>row-0</li>')
    expect(markup.match(/<li>/g)).toHaveLength(50)
  })

  test('search resets pagination and finds a record beyond the current page', () => {
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><TableHarness nextPage filterAfter /></I18nextProvider>)
    expect(markup).not.toContain('aria-label="Paginación"')
    expect(markup).toContain('<li>row-500</li>')
    expect(markup.match(/<li>/g)).toHaveLength(1)
  })

  test('pagination is shown only above 50 rows', () => {
    for (const count of [0, 15, 50, 51]) {
      const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><TableHarness count={count} /></I18nextProvider>)
      expect(markup.includes('aria-label="Paginación"')).toBe(count > 50)
      expect(markup).toContain('data-action="upload"')
    }
  })
})
