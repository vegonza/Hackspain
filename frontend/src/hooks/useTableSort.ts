import { useState } from 'react'

export function useTableSort<Column extends string>() {
  const [sortColumn, setSortColumn] = useState<Column | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')

  function onToggleSort(column: Column): void {
    if (sortColumn !== column) {
      setSortColumn(column)
      setSortDirection('asc')
    } else if (sortDirection === 'asc') {
      setSortDirection('desc')
    } else {
      setSortColumn(null)
      setSortDirection('asc')
    }
  }

  function sortRows<Row>(rows: Row[], value: (row: Row, column: Column) => string | number | null): Row[] {
    if (sortColumn === null) return rows
    const column = sortColumn
    return [...rows].sort((a, b) => {
      const left = value(a, column), right = value(b, column)
      if (left === null) return right === null ? 0 : 1
      if (right === null) return -1
      const comparison = typeof left === 'number' && typeof right === 'number'
        ? left - right
        : String(left).localeCompare(String(right), 'es', { numeric: true, sensitivity: 'base' })
      return sortDirection === 'asc' ? comparison : -comparison
    })
  }

  return { sortColumn, sortDirection, onToggleSort, sortRows }
}
