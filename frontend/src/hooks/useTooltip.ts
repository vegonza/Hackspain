import { useCallback, type PointerEvent as ReactPointerEvent, type RefCallback } from 'react'
import { useTooltipDelay } from '@/hooks/useTooltipDelay'

const VIEWPORT_PAD = 8
const TOOLTIP_GAP = 4

interface TooltipController {
  triggerRef: RefCallback<HTMLElement>
  open: boolean
  handlePointerEnter: (event: ReactPointerEvent<HTMLElement>) => void
  closeTooltip: () => void
  positionTooltip: RefCallback<HTMLDivElement>
}

export function useTooltip(onlyWhenTruncated: boolean): TooltipController {
  const { triggerRef, triggerElementRef, open, handlePointerEnter: showTooltip, closeTooltip } = useTooltipDelay()

  const handlePointerEnter = useCallback((event: ReactPointerEvent<HTMLElement>): void => {
    const element = event.currentTarget
    if (onlyWhenTruncated && element.scrollWidth <= element.clientWidth) return
    showTooltip(event)
  }, [onlyWhenTruncated, showTooltip])

  const positionTooltip = useCallback((element: HTMLDivElement | null): void => {
    if (element === null || triggerElementRef.current === null) return
    const bounds = triggerElementRef.current.getBoundingClientRect()
    const maxLeft = window.innerWidth - VIEWPORT_PAD - element.offsetWidth
    const left = Math.max(VIEWPORT_PAD, Math.min(bounds.left + bounds.width / 2 - element.offsetWidth / 2, maxLeft))
    const spaceBelow = window.innerHeight - bounds.bottom - VIEWPORT_PAD
    const top = spaceBelow >= element.offsetHeight + TOOLTIP_GAP
      ? bounds.bottom + TOOLTIP_GAP
      : bounds.top - element.offsetHeight - TOOLTIP_GAP
    element.style.left = `${left}px`
    element.style.top = `${Math.max(VIEWPORT_PAD, top)}px`
    element.style.visibility = 'visible'
  }, [triggerElementRef])

  return { triggerRef, open, handlePointerEnter, closeTooltip, positionTooltip }
}
