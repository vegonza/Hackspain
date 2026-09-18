import { Toaster } from '@/components/ui/sonner'
import { DocumentsPage } from '@/pages/DocumentsPage'
import type { Document } from '@/api/documents'

export function App({ initialDocuments }: { initialDocuments: Document[] }) {
  return (
    <>
      <Toaster position="top-center" duration={4000} />
      <DocumentsPage initialDocuments={initialDocuments} />
    </>
  )
}
