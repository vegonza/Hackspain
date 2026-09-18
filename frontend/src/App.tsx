import { Toaster } from '@/components/ui/sonner'
import { ExamplePage } from '@/pages/ExamplePage'

export function App() {
  return (
    <>
      <Toaster position="top-center" duration={4000} />
      <ExamplePage />
    </>
  )
}
