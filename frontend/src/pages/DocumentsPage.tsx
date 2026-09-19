import { DocumentsView } from '@/components/documents/DocumentsView'
import { useDocuments } from '@/hooks/useDocuments'
import { useErpSnapshot } from '@/hooks/useErpSnapshot'
import { useOrders } from '@/hooks/useOrders'
import { useSuppliers } from '@/hooks/useSuppliers'
import { useUsage } from '@/hooks/useUsage'
import { useTreasury } from '@/hooks/useTreasury'

export function DocumentsPage() {
  const documents = useDocuments()
  const usage = useUsage()
  const orders = useOrders()
  const suppliers = useSuppliers()
  const erp = useErpSnapshot()
  const treasury = useTreasury()
  return <DocumentsView {...documents} usage={usage} suppliers={suppliers} orders={orders} erp={erp} treasury={treasury} />
}
