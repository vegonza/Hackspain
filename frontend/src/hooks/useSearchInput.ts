import {
  useCallback,
  useRef,
  useState,
  type FocusEventHandler,
  type KeyboardEventHandler,
} from 'react'
import { flushSync } from 'react-dom'

const SEARCH_INPUT_MIN_WIDTH = 224

export function useSearchInput(collapsible: boolean) {
  const [collapsed, setCollapsed] = useState(false)
  const [forcedOpen, setForcedOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const resizeObserverRef = useRef<ResizeObserver | null>(null)
  const mutationObserverRef = useRef<MutationObserver | null>(null)

  const rootRef = useCallback((node: HTMLDivElement | null): void => {
    if (resizeObserverRef.current !== null) {
      resizeObserverRef.current.disconnect()
      resizeObserverRef.current = null
    }
    if (mutationObserverRef.current !== null) {
      mutationObserverRef.current.disconnect()
      mutationObserverRef.current = null
    }
    if (node === null) return

    const parent = node.parentElement as HTMLElement
    const measure = (): void => {
      const parentStyles = getComputedStyle(parent)
      const visibleChildren = Array.from(parent.children).filter((child) => (
        getComputedStyle(child).display !== 'none'
      ))
      const siblingWidth = visibleChildren.reduce((total, child) => (
        child === node ? total : total + child.getBoundingClientRect().width
      ), 0)
      const gap = Number.parseFloat(parentStyles.columnGap)
      const padding = Number.parseFloat(parentStyles.paddingLeft)
        + Number.parseFloat(parentStyles.paddingRight)
      const availableWidth = parent.clientWidth
        - padding
        - siblingWidth
        - gap * Math.max(visibleChildren.length - 1, 0)
      const nextCollapsed = collapsible && availableWidth < SEARCH_INPUT_MIN_WIDTH
      setCollapsed((current) => current === nextCollapsed ? current : nextCollapsed)
    }
    const observeChildren = (observer: ResizeObserver): void => {
      observer.disconnect()
      observer.observe(parent)
      Array.from(parent.children).forEach((child) => observer.observe(child))
    }

    const resizeObserver = new ResizeObserver(measure)
    observeChildren(resizeObserver)
    resizeObserverRef.current = resizeObserver

    const mutationObserver = new MutationObserver(() => {
      observeChildren(resizeObserver)
      measure()
    })
    mutationObserver.observe(parent, { childList: true, characterData: true, subtree: true })
    mutationObserverRef.current = mutationObserver
    measure()
  }, [collapsible])

  const openCollapsed = useCallback((): void => {
    flushSync(() => setForcedOpen(true))
    inputRef.current!.focus()
  }, [])

  const closeCollapsed = useCallback<FocusEventHandler<HTMLInputElement>>((): void => {
    setForcedOpen(false)
  }, [])

  const handleKeyDown = useCallback<KeyboardEventHandler<HTMLInputElement>>((event): void => {
    if (event.key !== 'Escape') return
    setForcedOpen(false)
    event.currentTarget.blur()
  }, [])

  return {
    collapsed,
    forcedOpen,
    rootRef,
    inputRef,
    openCollapsed,
    closeCollapsed,
    handleKeyDown,
  }
}
