import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Slot } from 'radix-ui'
import { useTooltip } from '@/hooks/useTooltip'
import { cn } from '@/lib/utils'

interface Props {
  text: ReactNode
  children: ReactNode
  className?: string
  asChild?: boolean
  onlyWhenTruncated?: boolean
}

export function Tooltip({ text, children, className, asChild = false, onlyWhenTruncated = false }: Props) {
  const { triggerRef, open, handlePointerEnter, closeTooltip, positionTooltip } = useTooltip(onlyWhenTruncated)
  const events = {
    onPointerEnter: handlePointerEnter,
    onPointerLeave: closeTooltip,
    onPointerDown: closeTooltip,
  }
  const trigger = asChild
    ? <Slot.Root ref={triggerRef} className={className} {...events}>{children}</Slot.Root>
    : <div ref={triggerRef} className={cn('min-w-0 max-w-full', className)} {...events}>{children}</div>

  return (
    <>
      {trigger}
      {open && createPortal(
        <div ref={positionTooltip} style={{ visibility: 'hidden' }} className="clover-tooltip">{text}</div>,
        document.body,
      )}
    </>
  )
}
