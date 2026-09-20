import { describe, expect, test } from 'bun:test'
import { invoiceCategoryIcon } from '../src/lib/invoiceCategory'
import otherIcon from '../src/assets/categories/11-otros.svg'

describe('invoice category icons', () => {
  test.each(['officeSupplies', 'maintenance', 'recurringServices', 'inspection', 'supplies', 'installation',
    'cleaning', 'transport', 'technicalSupport', 'professionalServices'] as const)('maps %s to its icon', category => {
    expect(invoiceCategoryIcon(category)).toContain('.svg')
  })

  test('uses the custom Otros icon for other concepts', () => {
    expect(invoiceCategoryIcon('other')).toBe(otherIcon)
  })
})
