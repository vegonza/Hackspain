import { InvoicesView } from '@/components/invoices/InvoicesView'
import { useInvoices } from '@/hooks/useInvoices'
import { useErpSnapshot } from '@/hooks/useErpSnapshot'
import { useOrders } from '@/hooks/useOrders'
import { useSuppliers } from '@/hooks/useSuppliers'
import { useClients } from '@/hooks/useClients'
import { useUsage } from '@/hooks/useUsage'
import { useAnalytics } from '@/hooks/useAnalytics'

export function InvoicesPage() {
  const invoices = useInvoices()
  const usage = useUsage()
  const orders = useOrders()
  const suppliers = useSuppliers()
  const erp = useErpSnapshot()
  const clients = useClients()
  const analytics = useAnalytics()
  return <InvoicesView {...invoices} usage={usage} suppliers={suppliers} orders={orders} erp={erp} clients={clients} analytics={analytics} />
}
