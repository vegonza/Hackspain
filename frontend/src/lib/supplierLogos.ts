import p001 from '@/assets/suppliers/p001-suministros-levante.svg'
import p002 from '@/assets/suppliers/p002-transportes-guadaira.svg'
import p003 from '@/assets/suppliers/p003-ofimatica-cieza.svg'
import p004 from '@/assets/suppliers/p004-limpiezas-turia.svg'
import p005 from '@/assets/suppliers/p005-catering-hermanos-pico.svg'
import p006 from '@/assets/suppliers/p006-electricidad-montcada.svg'
import p007 from '@/assets/suppliers/p007-papeleria-ruzafa.svg'
import p008 from '@/assets/suppliers/p008-seguridad-alcores.svg'
import p009 from '@/assets/suppliers/p009-construcciones-benimaclet.svg'
import p010 from '@/assets/suppliers/p010-informatica-benimamet.svg'
import p011 from '@/assets/suppliers/p011-mensajeria-rapida-del-sur.svg'
import p012 from '@/assets/suppliers/p012-muller-partner.svg'
import p013 from '@/assets/suppliers/p013-consulting-meridional.svg'
import p014 from '@/assets/suppliers/p014-servicos-aljarafe.svg'
import p015 from '@/assets/suppliers/p015-tokyo-systems.svg'
import consultoriaDocumentalAljarafe from '@/assets/suppliers/consultoria-documental-aljarafe.svg'
import consultoriaEstrategicaIberica from '@/assets/suppliers/consultoria-estrategica-iberica.svg'
import ireneSolutions from '@/assets/suppliers/irene-solutions.svg'
import bancoMiralmar from '@/assets/banco-miralmar.svg'

function normalizeSupplierName(name: string): string {
  return name.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().replace(/[^a-z0-9]/g, '')
}

const logosByName = new Map<string, string>([
  ['Suministros Levante S.L.', p001],
  ['Transportes Guadaira S.A.', p002],
  ['Ofimática Cieza S.L.', p003],
  ['Limpiezas Turia S.L.', p004],
  ['Catering Hermanos Pico S.L.', p005],
  ['Electricidad Montcada S.A.', p006],
  ['Papelería Ruzafa S.C.', p007],
  ['Seguridad Alcores S.L.', p008],
  ['Construcciones Benimaclet S.A.', p009],
  ['Informática Benimámet S.L.', p010],
  ['Mensajería Rápida del Sur S.L.', p011],
  ['Müller & Partner GmbH', p012],
  ['Consulting Méridional SARL', p013],
  ['Serviços Aljarafe Ltda', p014],
  ['Tokyo Systems K.K.', p015],
  ['Consultoría Documental Aljarafe S.L.', consultoriaDocumentalAljarafe],
  ['Consultoría Estratégica Ibérica S.L.', consultoriaEstrategicaIberica],
  ['IRENE SOLUTIONS SL', ireneSolutions],
  ['Banco Miralmar S.A.', bancoMiralmar],
].map(([name, logo]) => [normalizeSupplierName(name), logo]))

export function supplierLogo(name: string | null): string | undefined {
  if (name === null) return undefined
  return logosByName.get(normalizeSupplierName(name))
}
