import { useCallback, useRef, useState, type PointerEvent as ReactPointerEvent, type RefCallback, type RefObject } from 'react'

const TOOLTIP_DELAY_MS = 500
const TOOLTIP_SKIP_DELAY_MS = 300

let activeTooltipId: symbol | null = null
let skipDelayUntil = 0

interface TooltipDelayController {
  triggerRef: RefCallback<HTMLElement>
  triggerElementRef: RefObject<HTMLElement | null>
  open: boolean
  handlePointerEnter: (event: ReactPointerEvent<HTMLElement>) => void
  closeTooltip: () => void
}

export function useTooltipDelay(): TooltipDelayController {
  const tooltipIdRef = useRef(Symbol())
  const triggerElementRef = useRef<HTMLElement>(null)
  const openTimerRef = useRef<number | null>(null)
  const openRef = useRef(false)
  const [open, setOpen] = useState(false)

  const clearOpenTimer = useCallback((): void => {
    if (openTimerRef.current === null) return
    window.clearTimeout(openTimerRef.current)
    openTimerRef.current = null
  }, [])

  const showTooltip = useCallback((): void => {
    if (triggerElementRef.current === null) return
    openRef.current = true
    activeTooltipId = tooltipIdRef.current
    skipDelayUntil = Number.POSITIVE_INFINITY
    setOpen(true)
  }, [])

  const closeTooltip = useCallback((): void => {
    clearOpenTimer()
    if (openRef.current) {
      openRef.current = false
      if (activeTooltipId === tooltipIdRef.current) {
        activeTooltipId = null
        skipDelayUntil = Date.now() + TOOLTIP_SKIP_DELAY_MS
      }
    }
    setOpen(false)
  }, [clearOpenTimer])

  const triggerRef = useCallback<RefCallback<HTMLElement>>((element) => {
    triggerElementRef.current = element
    if (element !== null) return
    clearOpenTimer()
    openRef.current = false
  }, [clearOpenTimer])

  const handlePointerEnter = useCallback((event: ReactPointerEvent<HTMLElement>): void => {
    if (event.pointerType !== 'mouse') return
    clearOpenTimer()
    if (activeTooltipId !== null || Date.now() < skipDelayUntil) {
      showTooltip()
      return
    }
    openTimerRef.current = window.setTimeout(showTooltip, TOOLTIP_DELAY_MS)
  }, [clearOpenTimer, showTooltip])

  return { triggerRef, triggerElementRef, open, handlePointerEnter, closeTooltip }
}
