import officeSupplies from '@/assets/categories/01-material-de-oficina.svg'
import maintenance from '@/assets/categories/02-mantenimiento-reparacion.svg'
import recurringServices from '@/assets/categories/03-servicios-recurrentes.svg'
import inspection from '@/assets/categories/04-revision-inspeccion.svg'
import supplies from '@/assets/categories/05-suministros.svg'
import installation from '@/assets/categories/06-instalacion.svg'
import cleaning from '@/assets/categories/07-limpieza.svg'
import transport from '@/assets/categories/08-transporte.svg'
import technicalSupport from '@/assets/categories/09-soporte-tecnico.svg'
import professionalServices from '@/assets/categories/10-servicios-profesionales.svg'
import type { InvoiceCategory } from '@/api/invoices'

const categoryIcons: Partial<Record<InvoiceCategory, string>> = {
  officeSupplies,
  maintenance,
  recurringServices,
  inspection,
  supplies,
  installation,
  cleaning,
  transport,
  technicalSupport,
  professionalServices,
}

export function invoiceCategoryIcon(category: InvoiceCategory): string | null {
  return categoryIcons[category] ?? null
}
