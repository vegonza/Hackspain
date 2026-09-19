export const TABLE_PAGE_SIZE = 50

export function tablePage(total: number, requestedPage: number) {
  const pages = Math.max(1, Math.ceil(total / TABLE_PAGE_SIZE))
  const page = Math.max(0, Math.min(requestedPage, pages - 1))
  const start = page * TABLE_PAGE_SIZE
  return { page, pages, start, end: Math.min(total, start + TABLE_PAGE_SIZE), total }
}
