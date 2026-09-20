import { ChevronDown } from 'lucide-react'
import { Select as SelectPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

interface Props {
  value: string
  onValueChange: (value: string) => void
  options: readonly { value: string; label: string; count?: number }[]
  label: string
  placeholder?: string
  disabled?: boolean
  showChevron?: boolean
  className?: string
}

export function Select({ value, onValueChange, options, label, placeholder, disabled = false, showChevron = true, className }: Props) {
  return <SelectPrimitive.Root value={value} onValueChange={onValueChange} disabled={disabled}>
    <SelectPrimitive.Trigger className={cn('app-select-trigger', className)} aria-label={label}>
      <SelectPrimitive.Value placeholder={placeholder} />
      {showChevron && <SelectPrimitive.Icon asChild><ChevronDown size={14} /></SelectPrimitive.Icon>}
    </SelectPrimitive.Trigger>
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content className="app-select-content" position="popper" align="end" sideOffset={6} collisionPadding={8}>
        <SelectPrimitive.Viewport className="app-select-viewport">
          {options.map(option => <SelectPrimitive.Item key={option.value} value={option.value} className="app-select-option">
            <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
            {option.count !== undefined && <span className="app-select-count">{option.count}</span>}
          </SelectPrimitive.Item>)}
        </SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  </SelectPrimitive.Root>
}
