import { useCallback } from 'react'

const editingControls = 'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="combobox"], [role="slider"], [role="spinbutton"]'

export function useMonthShortcuts(disabled: boolean, onMove: (direction: -1 | 1) => void) {
  return useCallback((node: HTMLElement | null) => {
    if (node === null || disabled) return
    const document = node.ownerDocument
    function onKeyDown(event: KeyboardEvent): void {
      if (event.defaultPrevented || event.isComposing || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
      if (event.target instanceof Element && event.target.closest(editingControls) !== null) return
      if (document.querySelector('[role="dialog"], [role="listbox"], [role="menu"]') !== null) return
      event.preventDefault()
      onMove(event.key === 'ArrowLeft' ? -1 : 1)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [disabled, onMove])
}
