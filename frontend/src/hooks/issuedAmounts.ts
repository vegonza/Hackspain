import type { IssuedLine } from '@/api/issued'

function scaled(value: string, digits: number): bigint {
  if (value === '') return 0n
  const [whole, fraction = ''] = value.split('.')
  return BigInt(whole) * (10n ** BigInt(digits)) + BigInt(fraction.padEnd(digits, '0').slice(0, digits))
}

export function issuedTotals(items: IssuedLine[]) {
  const lines = items.map(item => {
    const base = (scaled(item.quantity, 4) * scaled(item.unit_price, 4) + 500000n) / 1000000n
    const tax = (base * scaled(item.tax_rate, 2) + 5000n) / 10000n
    return { base: Number(base) / 100, tax: Number(tax) / 100 }
  })
  const base = lines.reduce((sum, line) => sum + Math.round(line.base * 100), 0)
  const tax = lines.reduce((sum, line) => sum + Math.round(line.tax * 100), 0)
  return { lines, base: base / 100, tax: tax / 100, total: (base + tax) / 100 }
}
