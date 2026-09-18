import type { Document } from '@/api/documents'
import { DocumentsView } from '@/components/documents/DocumentsView'
import { useDocuments } from '@/hooks/useDocuments'

export function DocumentsPage({ initialDocuments }: { initialDocuments: Document[] }) {
  const documents = useDocuments(initialDocuments)
  return <DocumentsView {...documents} />
}
