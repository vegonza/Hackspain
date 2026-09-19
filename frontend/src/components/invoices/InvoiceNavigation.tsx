import { ToggleGroup } from 'radix-ui'

type Props = {
  label: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
}

export function InvoiceNavigation({ label, value, onChange, options }: Props) {
  return <ToggleGroup.Root type="single" className="invoice-pane-toggle" aria-label={label} value={value} onValueChange={onChange}>
    {options.map(option => <ToggleGroup.Item key={option.value} value={option.value}>{option.label}</ToggleGroup.Item>)}
  </ToggleGroup.Root>
}
