import { Trash2 } from 'lucide-react'
import { useHoldButton } from '@/hooks/useHoldButton'

interface Props {
  label: string
  disabled: boolean
  onConfirm: () => Promise<void>
}

export function HoldButton({ label, disabled, onConfirm }: Props) {
  const { ref, holding, cancel, onPointerDown, onKeyDown } = useHoldButton(onConfirm, disabled)
  return (
    <button ref={ref} type="button" className="hold-button" disabled={disabled}
      data-holding={holding} onPointerDown={onPointerDown} onPointerUp={cancel}
      onPointerCancel={cancel} onLostPointerCapture={cancel} onPointerLeave={cancel}
      onKeyDown={onKeyDown} onKeyUp={cancel} onBlur={cancel}>
      <span className="hold-progress" aria-hidden="true" />
      <Trash2 size={15} /><span>{label}</span>
    </button>
  )
}
