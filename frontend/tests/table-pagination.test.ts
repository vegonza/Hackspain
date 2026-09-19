import { describe, expect, test } from 'bun:test'
import { tablePage } from '../src/hooks/tablePagination'

describe('shared table pagination', () => {
  test('500 in-memory rows produce ten complete, non-overlapping pages', () => {
    const rows = Array.from({ length: 500 }, (_, index) => index)
    const visited: number[] = []
    for (let requested = 0; requested < 10; requested++) {
      const { start, end, pages } = tablePage(rows.length, requested)
      expect(pages).toBe(10)
      expect(end - start).toBe(50)
      visited.push(...rows.slice(start, end))
    }
    expect(visited).toEqual(rows)
  })

  test('search across the full collection can find rows outside the first page', () => {
    const rows = Array.from({ length: 500 }, (_, index) => `invoice-${index}.pdf`)
    const matches = rows.filter(name => name.includes('499'))
    const { start, end, pages } = tablePage(matches.length, 9)
    expect(matches.slice(start, end)).toEqual(['invoice-499.pdf'])
    expect(pages).toBe(1)
  })

  test('shrinking collections clamp to the last valid page', () => {
    expect(tablePage(101, 9)).toEqual({ page: 2, pages: 3, start: 100, end: 101, total: 101 })
    expect(tablePage(100, 2)).toEqual({ page: 1, pages: 2, start: 50, end: 100, total: 100 })
  })

  test('empty and single-page tables have valid ranges', () => {
    expect(tablePage(0, 5)).toEqual({ page: 0, pages: 1, start: 0, end: 0, total: 0 })
    expect(tablePage(50, -1)).toEqual({ page: 0, pages: 1, start: 0, end: 50, total: 50 })
  })
})
