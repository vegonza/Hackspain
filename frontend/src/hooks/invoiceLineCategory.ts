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

const categories = [
  { id: 'officeSupplies', icon: officeSupplies, pattern: /^(?:material de oficina|consumibles)\b/ },
  { id: 'maintenance', icon: maintenance, pattern: /^(?:mantenimiento|reparacion|servicio (?:anual|mensual|trimestral) de mantenimiento)\b/ },
  { id: 'recurringServices', icon: recurringServices, pattern: /^(?:servicio mensual|cuota de servicio)\b/ },
  { id: 'inspection', icon: inspection, pattern: /^(?:revision (?:anual|tecnica)|inspeccion)\b/ },
  { id: 'supplies', icon: supplies, pattern: /^suministros?\b/ },
  { id: 'installation', icon: installation, pattern: /^instalacion\b/ },
  { id: 'cleaning', icon: cleaning, pattern: /^(?:servicio de limpieza|limpieza)\b/ },
  { id: 'transport', icon: transport, pattern: /^transporte\b/ },
  { id: 'technicalSupport', icon: technicalSupport, pattern: /^(?:horas de soporte|soporte tecnico)\b/ },
  { id: 'professionalServices', icon: professionalServices, pattern: /^(?:servicios? profesional(?:es)?|servicos profissionais|professionelle dienstleistung|professional services|services professionnels|servizi professionali|servei professional)\b/ },
] as const

export function invoiceLineCategory(description: string) {
  const normalized = description.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/^\s*[-–—•]\s*/, '').trim().replace(/\s+/g, ' ')
  return categories.find(category => category.pattern.test(normalized))
}
