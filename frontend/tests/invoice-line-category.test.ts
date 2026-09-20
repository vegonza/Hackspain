import { describe, expect, test } from 'bun:test'
import { invoiceLineCategory } from '../src/hooks/invoiceLineCategory'

describe('invoice line categories', () => {
  test.each([
    ['Material de oficina x1', 'officeSupplies'],
    ['Consumibles (1 ud)', 'officeSupplies'],
    ['Mantenimiento trimestral', 'maintenance'],
    ['Reparación equipo (1)', 'maintenance'],
    ['Servicio mensual', 'recurringServices'],
    ['Cuota de servicio (1 ud)', 'recurringServices'],
    ['Revisión anual x1', 'inspection'],
    ['Suministro pedido', 'supplies'],
    ['Instalación (1)', 'installation'],
    ['Servicio de limpieza', 'cleaning'],
    ['Transporte urgente', 'transport'],
    ['Horas de soporte', 'technicalSupport'],
    ['Servicio profesional', 'professionalServices'],
    ['Servicios profesionales', 'professionalServices'],
  ])('categorizes %s as %s', (description, category) => {
    expect(invoiceLineCategory(description)!.id).toBe(category)
  })

  test.each(['Serviços profissionais', 'Professionelle Dienstleistung', 'Professional services',
    'Services professionnels', 'Servizi professionali', 'Servei professional'])('recognizes international service description %s', description => {
    expect(invoiceLineCategory(description)!.id).toBe('professionalServices')
  })

  test('handles extraction formatting without modifying the description', () => {
    for (const description of ['  - REVISIÓN ANUAL (1 ud)  ', '• Revisión   anual x1', 'Revisio\u0301n anual']) {
      expect(invoiceLineCategory(description)!.id).toBe('inspection')
    }
  })

  test('uses the specific service category before a recurring-service match', () => {
    expect(invoiceLineCategory('Servicio mensual de mantenimiento (1 ud)')!.id).toBe('maintenance')
    expect(invoiceLineCategory('Servicio anual de mantenimiento (1 ud)')!.id).toBe('maintenance')
  })

  test.each(['Ajuste por redondeo', 'Escalar a revisión humana', 'Bloquear conciliacion hasta revision manual (1 ud)',
    'Diferencia de importe autorizada', 'Transporteador', ''])('leaves %s uncategorized', description => {
    expect(invoiceLineCategory(description)).toBeUndefined()
  })
})
