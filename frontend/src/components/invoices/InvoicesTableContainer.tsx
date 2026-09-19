import { InvoicesTable, type InvoicesTableProps } from '@/components/invoices/InvoicesTable'
import { useInvoiceTable } from '@/hooks/useInvoiceTable'
import type { useInvoices } from '@/hooks/useInvoices'

type Props = Omit<InvoicesTableProps, 'table'> & { rows: ReturnType<typeof useInvoices>['filteredInvoices'] }

export function InvoicesTableContainer({ rows, ...props }: Props) {
  const table = useInvoiceTable({ filteredInvoices: rows, search: props.search,
    sortColumn: props.sortColumn, sortDirection: props.sortDirection })
  return <InvoicesTable {...props} table={table} />
}
