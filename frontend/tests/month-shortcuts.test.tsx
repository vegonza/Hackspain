import { afterEach, describe, expect, mock, test } from 'bun:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { useMonthShortcuts } from '../src/hooks/useMonthShortcuts'

const originalElement = Object.getOwnPropertyDescriptor(globalThis, 'Element')

afterEach(() => {
  if (originalElement === undefined) Reflect.deleteProperty(globalThis, 'Element')
  else Object.defineProperty(globalThis, 'Element', originalElement)
})

class FocusTarget extends EventTarget {
  constructor(readonly selector: string) { super() }
  closest(selector: string): FocusTarget | null {
    return selector.split(', ').includes(this.selector) ? this : null
  }
}

function environment(disabled = false) {
  Object.defineProperty(globalThis, 'Element', { configurable: true, value: FocusTarget })
  const ownerDocument = Object.assign(new EventTarget(), { querySelector: mock((): object | null => null) })
  const onMove = mock((direction: -1 | 1) => direction)
  let mount: ReturnType<typeof useMonthShortcuts>
  function Harness() {
    mount = useMonthShortcuts(disabled, onMove)
    return null
  }
  renderToStaticMarkup(<Harness />)
  const cleanup = mount!({ ownerDocument } as unknown as HTMLElement)
  function press(key: string, properties: Record<string, unknown> = {}, target = new FocusTarget('button')): Event {
    const event = Object.assign(new Event('keydown', { cancelable: true }), {
      key, altKey: false, ctrlKey: false, metaKey: false, shiftKey: false, isComposing: false, ...properties,
    })
    Object.defineProperty(event, 'target', { value: target })
    ownerDocument.dispatchEvent(event)
    return event
  }
  return { ownerDocument, onMove, cleanup, press }
}

describe('month shortcuts', () => {
  test('left and right navigate months and prevent horizontal scrolling', () => {
    const { press, onMove, cleanup } = environment()
    expect(press('ArrowLeft').defaultPrevented).toBe(true)
    expect(press('ArrowRight').defaultPrevented).toBe(true)
    expect(press('ArrowRight', { repeat: true }).defaultPrevented).toBe(true)
    expect(onMove.mock.calls.map(([direction]) => direction)).toEqual([-1, 1, 1])
    cleanup!()
  })

  test('typing and selection controls retain their arrow keys', () => {
    const { press, onMove, cleanup } = environment()
    for (const selector of ['input', 'textarea', 'select', '[contenteditable]:not([contenteditable="false"])', '[role="combobox"]', '[role="textbox"]']) {
      expect(press('ArrowLeft', {}, new FocusTarget(selector)).defaultPrevented).toBe(false)
      expect(press('ArrowRight', {}, new FocusTarget(selector)).defaultPrevented).toBe(false)
    }
    expect(onMove).not.toHaveBeenCalled()
    cleanup!()
  })

  test('modified keys, composition and handled events are left alone', () => {
    const { press, onMove, ownerDocument, cleanup } = environment()
    for (const key of ['altKey', 'ctrlKey', 'metaKey', 'shiftKey', 'isComposing']) {
      expect(press('ArrowRight', { [key]: true }).defaultPrevented).toBe(false)
    }
    press('ArrowDown')
    const handled = Object.assign(new Event('keydown', { cancelable: true }), { key: 'ArrowLeft' })
    handled.preventDefault()
    ownerDocument.dispatchEvent(handled)
    expect(onMove).not.toHaveBeenCalled()
    cleanup!()
  })

  test('an open dropdown or confirmation prevents background month changes', () => {
    const { press, onMove, ownerDocument, cleanup } = environment()
    ownerDocument.querySelector.mockReturnValue({})
    expect(press('ArrowLeft').defaultPrevented).toBe(false)
    expect(onMove).not.toHaveBeenCalled()
    cleanup!()
  })

  test('disabled views install no shortcuts and unmount removes the listener', () => {
    const disabled = environment(true)
    disabled.press('ArrowRight')
    expect(disabled.onMove).not.toHaveBeenCalled()
    expect(disabled.cleanup).toBeUndefined()
    const active = environment()
    active.press('ArrowRight')
    active.cleanup!()
    active.press('ArrowRight')
    expect(active.onMove).toHaveBeenCalledTimes(1)
  })
})
