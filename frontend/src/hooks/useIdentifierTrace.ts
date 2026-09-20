import { useTranslation } from 'react-i18next'
import type { IdentifierCorrection } from '@/api/invoices'

export interface IdentifierTraceEntry {
  label: string
  characters: { value: string; changed: boolean }[]
}

export function useIdentifierTrace(corrections: IdentifierCorrection[]) {
  const { t } = useTranslation()
  const trace: Record<'supplier_nif' | 'iban', IdentifierTraceEntry | null> = { supplier_nif: null, iban: null }
  for (const correction of corrections) {
    const ignored = correction.field === 'supplier_nif' ? /[\s./-]/u : /\s/u
    const corrected = [...correction.corrected].filter(character => !ignored.test(character))
    let position = 0
    trace[correction.field] = {
      label: t('extraction.identifierCorrection'),
      characters: [...correction.original].map(value => {
        if (ignored.test(value)) return { value, changed: false }
        const changed = value.toUpperCase() !== corrected[position].toUpperCase()
        position += 1
        return { value, changed }
      }),
    }
  }
  return trace
}
