import { DocumentsView } from '@/components/documents/DocumentsView'
import { useDocuments } from '@/hooks/useDocuments'
import { useUsage } from '@/hooks/useUsage'

export function DocumentsPage() {
  const documents = useDocuments()
  const usage = useUsage()
  return <DocumentsView {...documents} usage={usage} />
}
