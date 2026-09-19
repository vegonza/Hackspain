import { Toaster } from '@/components/ui/sonner'
import { DocumentsPage } from '@/pages/DocumentsPage'

export function App() {
  return (
    <>
      <Toaster position="top-center" duration={4000} />
      <DocumentsPage />
    </>
  )
}
