import { useCallback, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { usePdfZoom } from '@/hooks/usePdfZoom'

const RENDER_BUFFER = 4
const PAGE_VISIBILITY_THRESHOLDS = [0, 0.25, 0.5, 0.75, 1]

export function usePdfViewer(url: string) {
  const { t } = useTranslation()
  const [pageCount, setPageCount] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [renderedPages, setRenderedPages] = useState<Set<number>>(() => new Set())
  const [aspectRatios, setAspectRatios] = useState<Record<number, number>>({})
  const [failed, setFailed] = useState(false)
  const { zoom, pageWidth, scrollRef, initScroll, setInner, zoomIn, zoomOut, ZOOM_MIN, ZOOM_MAX } = usePdfZoom()
  const observers = useRef(new Map<number, IntersectionObserver>())
  const visibility = useRef(new Map<number, number>())
  const pageCountRef = useRef(0)

  const renderPagesAround = useCallback((center: number, total: number) => {
    const start = Math.max(1, center - RENDER_BUFFER)
    const end = Math.min(total, center + RENDER_BUFFER)
    const pages = Array.from({ length: end - start + 1 }, (_, index) => start + index)
    setRenderedPages(current => current.size === pages.length && pages.every(page => current.has(page))
      ? current : new Set(pages))
  }, [])

  const containerRef = useCallback((element: HTMLDivElement | null) => {
    if (!element) return
    initScroll(element)
    return () => {
      initScroll(null)
      for (const observer of observers.current.values()) observer.disconnect()
      observers.current.clear()
      visibility.current.clear()
    }
  }, [initScroll])

  const registerPage = useCallback((page: number, node: HTMLDivElement | null) => {
    const previous = observers.current.get(page)
    if (previous) previous.disconnect()
    observers.current.delete(page)
    visibility.current.delete(page)
    if (!node) return
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting && entry.intersectionRatio > 0) visibility.current.set(page, entry.intersectionRatio)
        else visibility.current.delete(page)
      }
      let bestPage = 0
      let bestRatio = 0
      for (const [visiblePage, ratio] of visibility.current) {
        if (ratio > bestRatio) {
          bestRatio = ratio
          bestPage = visiblePage
        }
      }
      if (bestPage > 0) {
        setCurrentPage(bestPage)
        renderPagesAround(bestPage, pageCountRef.current)
      }
    }, { root: scrollRef.current, threshold: PAGE_VISIBILITY_THRESHOLDS })
    observer.observe(node)
    observers.current.set(page, observer)
  }, [renderPagesAround, scrollRef])

  const pageRefs = useMemo(() => Array.from({ length: pageCount }, (_, index) =>
    (node: HTMLDivElement | null) => registerPage(index + 1, node)), [pageCount, registerPage])

  function onLoadSuccess({ numPages }: { numPages: number }) {
    setPageCount(numPages)
    pageCountRef.current = numPages
    setCurrentPage(1)
    renderPagesAround(1, numPages)
  }

  function onPageLoad({ pageNumber, originalWidth, originalHeight }: { pageNumber: number; originalWidth: number; originalHeight: number }) {
    const ratio = originalHeight / originalWidth
    setAspectRatios(current => current[pageNumber] === ratio ? current : { ...current, [pageNumber]: ratio })
  }

  function onError() {
    setFailed(true)
    toast.error(t('invoices.pdfError'))
  }

  const pages = Array.from({ length: pageCount }, (_, index) => ({
    number: index + 1,
    ref: pageRefs[index],
    shouldRender: renderedPages.has(index + 1),
    aspectRatio: aspectRatios[index + 1] === undefined ? 11 / 8.5 : aspectRatios[index + 1],
  }))

  return {
    containerRef, setInner, file: url, pageWidth, pages, pageCount, currentPage, failed,
    zoom, zoomIn, zoomOut, zoomMin: ZOOM_MIN, zoomMax: ZOOM_MAX, onLoadSuccess, onPageLoad, onError,
    labels: { loading: t('invoices.loading'), error: t('invoices.pdfError'), zoomIn: t('invoices.zoomIn'), zoomOut: t('invoices.zoomOut') },
  }
}
