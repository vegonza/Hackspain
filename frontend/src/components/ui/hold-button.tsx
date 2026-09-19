import type { ComponentProps } from 'react'
import { useHoldButton } from '@/hooks/useHoldButton'
import { cn } from '@/lib/utils'

export function HoldButton({ onConfirm, children, className, disabled = false, ref, ...props }: ComponentProps<'button'> & { onConfirm: () => void }) {
  const hold = useHoldButton(onConfirm, disabled, ref)
  return <button {...props} ref={hold.mount} type="button" disabled={disabled}
    className={cn('relative overflow-hidden', className)}
    onPointerDown={hold.onPointerDown} onPointerUp={hold.cancel} onPointerLeave={hold.cancel} onPointerCancel={hold.cancel}
    onKeyDown={hold.onKeyDown} onKeyUp={hold.onKeyUp} onBlur={hold.cancel} onClick={event => event.preventDefault()}>
    <span aria-hidden className="pointer-events-none absolute inset-0 origin-left bg-destructive/15"
      style={{ transform: `scaleX(${hold.holding ? 1 : 0})`, transition: hold.holding ? 'transform 800ms linear' : 'none' }} />
    {children}
  </button>
}
