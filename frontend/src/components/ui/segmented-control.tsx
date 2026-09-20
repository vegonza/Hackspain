import type { ReactNode } from 'react'
import { ToggleGroup } from 'radix-ui'
import { useSegmentedControl } from '@/hooks/useSegmentedControl'
import { cn } from '@/lib/utils'

interface SegmentedControlProps<TValue extends string> {
  value: TValue
  onValueChange: (value: TValue) => void
  options: readonly { value: TValue; label: string; icon?: ReactNode; disabled?: boolean }[]
  label: string
  disabled?: boolean
  className?: string
}

export function SegmentedControl<TValue extends string>({ value, onValueChange, options, label, disabled, className }: SegmentedControlProps<TValue>) {
  const selectValue = useSegmentedControl(onValueChange)
  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={selectValue}
      disabled={disabled}
      aria-label={label}
      className={cn('grid w-fit max-w-full grid-flow-col auto-cols-fr gap-0.5 rounded-full bg-muted p-1', className)}
    >
      {options.map((option) => (
        <ToggleGroup.Item
          key={option.value}
          value={option.value}
          disabled={option.disabled}
          className="flex min-h-8 min-w-0 items-center justify-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-40 data-[state=on]:bg-background data-[state=on]:text-foreground data-[state=on]:shadow-sm"
        >
          {option.icon}
          <span className="truncate">{option.label}</span>
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  )
}
