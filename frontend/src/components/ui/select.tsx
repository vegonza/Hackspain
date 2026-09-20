import { ChevronDown } from 'lucide-react'
import { Select as SelectPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

interface Props {
  value: string
  onValueChange: (value: string) => void
  options: readonly { value: string; label: string; count?: number; logoUrl?: string }[]
  label: string
  placeholder?: string
  disabled?: boolean
  showChevron?: boolean
  className?: string
  contentClassName?: string
  align?: 'start' | 'center' | 'end'
}

export function Select({ value, onValueChange, options, label, placeholder, disabled = false, showChevron = true, className, contentClassName, align = 'end' }: Props) {
  return <SelectPrimitive.Root value={value} onValueChange={onValueChange} disabled={disabled}>
    <SelectPrimitive.Trigger className={cn('app-select-trigger', className)} aria-label={label}>
      <SelectPrimitive.Value placeholder={placeholder} />
      {showChevron && <SelectPrimitive.Icon asChild><ChevronDown size={14} /></SelectPrimitive.Icon>}
    </SelectPrimitive.Trigger>
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content className={cn('app-select-content', contentClassName)} position="popper" align={align} sideOffset={6} collisionPadding={8}>
        <SelectPrimitive.Viewport className="app-select-viewport">
          {options.map(option => <SelectPrimitive.Item key={option.value} value={option.value} textValue={option.label} className="app-select-option">
            <SelectPrimitive.ItemText>{option.logoUrl === undefined ? option.label : <span className="app-select-option-label">
              <img src={option.logoUrl} alt="" className="app-select-logo" /><span>{option.label}</span>
            </span>}</SelectPrimitive.ItemText>
            {option.count !== undefined && <span className="app-select-count">{option.count}</span>}
          </SelectPrimitive.Item>)}
        </SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  </SelectPrimitive.Root>
}
