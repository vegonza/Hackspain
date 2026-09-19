import type { Document } from '@/api/documents'
import { DocumentsView } from '@/components/documents/DocumentsView'
import { useDocuments } from '@/hooks/useDocuments'
import { useUsage } from '@/hooks/useUsage'

export function DocumentsPage({ initialDocuments }: { initialDocuments: Document[] }) {
  const documents = useDocuments(initialDocuments)
  const usage = useUsage()
  return <DocumentsView {...documents} usage={usage} />
}
