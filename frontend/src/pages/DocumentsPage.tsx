import { DocumentsView } from '@/components/documents/DocumentsView'
import { useDocuments } from '@/hooks/useDocuments'
import { useOrders } from '@/hooks/useOrders'
import { useSuppliers } from '@/hooks/useSuppliers'
import { useUsage } from '@/hooks/useUsage'

export function DocumentsPage() {
  const documents = useDocuments()
  const usage = useUsage()
  const orders = useOrders()
  const suppliers = useSuppliers()
  return <DocumentsView {...documents} usage={usage} suppliers={suppliers} orders={orders} />
}
