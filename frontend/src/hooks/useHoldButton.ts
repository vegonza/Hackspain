import { useCallback, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'

export function useHoldButton(onConfirm: () => Promise<void>, disabled: boolean) {
  const [holding, setHolding] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const ref = useCallback(() => () => {
    if (timer.current !== null) clearTimeout(timer.current)
  }, [])

  function cancel() {
    if (timer.current !== null) clearTimeout(timer.current)
    timer.current = null
    setHolding(false)
  }

  function start() {
    if (disabled || timer.current !== null) return
    setHolding(true)
    timer.current = setTimeout(() => {
      timer.current = null
      setHolding(false)
      void onConfirm()
    }, 900)
  }

  function onPointerDown(event: PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return
    event.currentTarget.setPointerCapture(event.pointerId)
    start()
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== ' ' && event.key !== 'Enter') return
    event.preventDefault()
    if (!event.repeat) start()
  }

  return { ref, holding, cancel, onPointerDown, onKeyDown }
}
