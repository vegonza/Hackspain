export type ErpSortColumn = 'entry' | 'order' | 'supplier' | 'taxId' | 'status' | 'date' | 'amount' | 'warnings'

export interface ErpRow {
  id: string
  href: string
  entryId: string
  orderId: string
  supplierId: string
  taxId: string
  status: string
  statusLabel: string
  dateLabel: string
  dateValue: number | null
  amountLabel: string
  amountValue: number | null
  warningLabels: string[]
}

export function filterErpRows(rows: ErpRow[], search: string): ErpRow[] {
  const query = search.trim().toLocaleLowerCase()
  return rows.filter(row => [row.entryId, row.orderId, row.supplierId, row.taxId, row.statusLabel, row.dateLabel, row.amountLabel, ...row.warningLabels]
    .some(value => value.toLocaleLowerCase().includes(query)))
}

export function erpSortValue(row: ErpRow, column: ErpSortColumn): string | number | null {
  switch (column) {
    case 'entry': return row.entryId
    case 'order': return row.orderId
    case 'supplier': return row.supplierId
    case 'taxId': return row.taxId
    case 'status': return row.statusLabel
    case 'date': return row.dateValue
    case 'amount': return row.amountValue
    case 'warnings': return row.warningLabels.length
  }
}
