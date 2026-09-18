import { useCallback, useRef, useState } from 'react'

const ZOOM_STEP = 0.1
const ZOOM_MIN = 1
const ZOOM_MAX = 5
const WHEEL_ZOOM_SENSITIVITY = 0.008

function getContentWidth(node: HTMLDivElement): number {
  const styles = window.getComputedStyle(node)
  return node.clientWidth
    - Number.parseFloat(styles.paddingLeft)
    - Number.parseFloat(styles.paddingRight)
}

function clampZoom(value: number): number {
  return Math.min(Math.max(value, ZOOM_MIN), ZOOM_MAX)
}

export function usePdfZoom() {
  const [zoom, setZoom] = useState(1)
  const [containerWidth, setContainerWidth] = useState(0)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const innerRef = useRef<HTMLDivElement | null>(null)
  const resizeObserverRef = useRef<ResizeObserver | null>(null)
  const wheelHandlerRef = useRef<((event: WheelEvent) => void) | null>(null)
  const liveZoomRef = useRef(1)

  const applyZoom = useCallback((value: number, anchorX: number, anchorY: number): void => {
    const container = scrollRef.current
    const inner = innerRef.current
    if (container === null || inner === null) return

    const previous = liveZoomRef.current
    const next = clampZoom(value)
    if (next === previous) return

    const ratio = next / previous
    liveZoomRef.current = next
    inner.style.zoom = next === 1 ? '' : `${next}`
    container.scrollLeft = (container.scrollLeft + anchorX) * ratio - anchorX
    container.scrollTop = (container.scrollTop + anchorY) * ratio - anchorY
    if (next > 1) container.setAttribute('data-pdf-zoomed', '')
    else container.removeAttribute('data-pdf-zoomed')
    setZoom(next)
  }, [])

  const removeScrollListeners = useCallback((): void => {
    if (resizeObserverRef.current !== null) resizeObserverRef.current.disconnect()
    resizeObserverRef.current = null
    if (scrollRef.current !== null && wheelHandlerRef.current !== null) {
      scrollRef.current.removeEventListener('wheel', wheelHandlerRef.current)
    }
    wheelHandlerRef.current = null
  }, [])

  const initScroll = useCallback((node: HTMLDivElement | null): void => {
    removeScrollListeners()
    scrollRef.current = node
    if (node === null) return

    const resizeObserver = new ResizeObserver((entries) => {
      setContainerWidth(getContentWidth(entries[0].target as HTMLDivElement))
    })
    resizeObserver.observe(node)
    resizeObserverRef.current = resizeObserver

    const wheelHandler = (event: WheelEvent): void => {
      if (!event.ctrlKey && !event.metaKey) return
      event.preventDefault()
      const rectangle = node.getBoundingClientRect()
      const factor = Math.exp(-event.deltaY * WHEEL_ZOOM_SENSITIVITY)
      applyZoom(
        liveZoomRef.current * factor,
        event.clientX - rectangle.left,
        event.clientY - rectangle.top,
      )
    }
    node.addEventListener('wheel', wheelHandler, { passive: false })
    wheelHandlerRef.current = wheelHandler
  }, [applyZoom, removeScrollListeners])

  const setInner = useCallback((node: HTMLDivElement | null): void => {
    innerRef.current = node
    if (node !== null) {
      node.style.zoom = liveZoomRef.current === 1 ? '' : `${liveZoomRef.current}`
      const container = scrollRef.current
      if (container !== null) setContainerWidth(getContentWidth(container))
    }
  }, [])

  const zoomTo = useCallback((value: number): void => {
    const container = scrollRef.current
    if (container === null) return
    applyZoom(value, container.clientWidth / 2, container.clientHeight / 2)
  }, [applyZoom])

  const zoomIn = useCallback((): void => zoomTo(liveZoomRef.current + ZOOM_STEP), [zoomTo])
  const zoomOut = useCallback((): void => zoomTo(liveZoomRef.current - ZOOM_STEP), [zoomTo])

  return {
    zoom,
    containerWidth,
    scrollRef,
    pageWidth: containerWidth > 0 ? containerWidth : undefined,
    zoomIn,
    zoomOut,
    initScroll,
    setInner,
    ZOOM_MIN,
    ZOOM_MAX,
  }
}
