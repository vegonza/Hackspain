import { ExampleView } from '@/components/example/ExampleView'
import { useExample } from '@/hooks/useExample'

export function ExamplePage() {
  const example = useExample()
  return <ExampleView {...example} />
}
