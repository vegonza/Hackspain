import { describe, expect, test } from 'bun:test'
import { invoiceCategoryIcon } from '../src/lib/invoiceCategory'

describe('invoice category icons', () => {
  test.each(['officeSupplies', 'maintenance', 'recurringServices', 'inspection', 'supplies', 'installation',
    'cleaning', 'transport', 'technicalSupport', 'professionalServices'] as const)('maps %s to its icon', category => {
    expect(invoiceCategoryIcon(category)).toContain('.svg')
  })

  test('does not invent an icon for other concepts', () => {
    expect(invoiceCategoryIcon('other')).toBeNull()
  })
})
