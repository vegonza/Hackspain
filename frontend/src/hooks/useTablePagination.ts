import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { tablePage } from '@/hooks/tablePagination'

export function useTablePagination<T>(rows: readonly T[], resetKey = '') {
  const { t } = useTranslation()
  const [selection, setSelection] = useState({ page: 0, resetKey })
  const { page, pages, start, end, total, pageRows } = useMemo(() => {
    const range = tablePage(rows.length, selection.resetKey === resetKey ? selection.page : 0)
    return { ...range, pageRows: rows.slice(range.start, range.end) }
  }, [rows, selection, resetKey])
  if (selection.resetKey !== resetKey || selection.page !== page) setSelection({ page, resetKey })
  return {
    rows: pageRows, pageKey: JSON.stringify([page, resetKey]),
    pagination: {
      page, pages,
      previousDisabled: page === 0, nextDisabled: page + 1 >= pages,
      onPrevious: () => setSelection({ page: Math.max(0, page - 1), resetKey }),
      onNext: () => setSelection({ page: Math.min(pages - 1, page + 1), resetKey }),
      label: t('pagination.label'), previousLabel: t('pagination.previous'), nextLabel: t('pagination.next'),
      rangeLabel: t('pagination.range', { start: total === 0 ? 0 : start + 1, end, total }),
      pageLabel: t('pagination.page', { page: page + 1, pages }),
    },
  }
}
