import { describe, expect, test } from 'bun:test'
import { supplierLogo } from '../src/lib/supplierLogos'
import companies from '../../svgs/companies/generations.json'

describe('supplier branding', () => {
  test.each(companies.generations.map(company => [company.supplier.legal_name, company.filename]))(
    'connects the generated logo for %s', (name, filename) => {
      expect(supplierLogo(name)).toContain(filename)
    },
  )

  test('matches capitalization, accents, punctuation and spacing in extracted names', () => {
    expect(supplierLogo('  CONSULTORIA   ESTRATEGICA IBERICA SL '))
      .toBe(supplierLogo('Consultoría Estratégica Ibérica S.L.'))
    expect(supplierLogo('MENSAJERÍA RÁPIDA DEL SUR S.L.'))
      .toBe(supplierLogo('Mensajería Rápida del Sur S.L.'))
    expect(supplierLogo('Muller & Partner GmbH')).toBe(supplierLogo('Müller & Partner GmbH'))
  })

  test('keeps companies sharing a place name distinct', () => {
    expect(supplierLogo('Consultoría Documental Aljarafe S.L.')).not.toBe(supplierLogo('Serviços Aljarafe Ltda'))
  })

  test('does not assign another company logo to an unknown or absent name', () => {
    expect(supplierLogo('Consultoría nueva S.L.')).toBeUndefined()
    expect(supplierLogo('Consultoría Estratégica Ibérica S.A.')).toBeUndefined()
    expect(supplierLogo(null)).toBeUndefined()
    expect(supplierLogo('')).toBeUndefined()
  })
})
