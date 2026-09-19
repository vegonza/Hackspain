import type { IdentifierTraceEntry } from '@/hooks/useIdentifierTrace'

export function InvoiceIdentifierTooltip({ label, characters }: IdentifierTraceEntry) {
  return <span>{label}{' '}<span className="whitespace-pre font-mono">{characters.map((character, index) => character.changed
    ? <span key={index} className="text-yellow-400">{character.value}</span>
    : <span key={index}>{character.value}</span>)}</span></span>
}
