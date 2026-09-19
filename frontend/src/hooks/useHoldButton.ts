import { useCallback, useRef, useState, type KeyboardEvent, type PointerEvent, type Ref } from 'react'

export function useHoldButton(onConfirm: () => void, disabled: boolean, forwardedRef: Ref<HTMLButtonElement> | undefined) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [holding, setHolding] = useState(false)
  const cancel = useCallback(() => {
    if (timer.current !== null) clearTimeout(timer.current)
    timer.current = null
    setHolding(false)
  }, [])
  const mount = useCallback((node: HTMLButtonElement | null) => {
    if (node === null) return
    const cleanup = typeof forwardedRef === 'function' ? forwardedRef(node) : undefined
    if (forwardedRef && typeof forwardedRef !== 'function') forwardedRef.current = node
    return () => {
      if (timer.current !== null) clearTimeout(timer.current)
      timer.current = null
      if (typeof cleanup === 'function') cleanup()
      else if (typeof forwardedRef === 'function') forwardedRef(null)
      else if (forwardedRef) forwardedRef.current = null
    }
  }, [forwardedRef])
  function start(): void {
    if (disabled || timer.current !== null) return
    setHolding(true)
    timer.current = setTimeout(() => {
      cancel()
      onConfirm()
    }, 800)
  }
  return {
    holding, mount, cancel,
    onPointerDown: (event: PointerEvent<HTMLButtonElement>) => {
      if (event.button === 0) start()
    },
    onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === ' ' || event.key === 'Enter') {
        event.preventDefault()
        if (!event.repeat) start()
      }
    },
    onKeyUp: (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === ' ' || event.key === 'Enter') cancel()
    },
  }
}
