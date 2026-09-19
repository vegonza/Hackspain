import { Toaster } from '@/components/ui/sonner'
import { InvoicesPage } from '@/pages/InvoicesPage'

export function App() {
  return (
    <>
      <Toaster position="bottom-right" duration={4000} />
      <InvoicesPage />
    </>
  )
}
