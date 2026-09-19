import { DocumentsView } from '@/components/documents/DocumentsView'
import { useDocuments } from '@/hooks/useDocuments'
import { useSuppliers } from '@/hooks/useSuppliers'
import { useUsage } from '@/hooks/useUsage'

export function DocumentsPage() {
  const documents = useDocuments()
  const usage = useUsage()
  const suppliers = useSuppliers()
  return <DocumentsView {...documents} usage={usage} suppliers={suppliers} />
}
