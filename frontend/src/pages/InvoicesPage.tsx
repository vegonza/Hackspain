import { InvoicesView } from '@/components/invoices/InvoicesView'
import { useInvoices } from '@/hooks/useInvoices'
import { useErpSnapshot } from '@/hooks/useErpSnapshot'
import { useOrders } from '@/hooks/useOrders'
import { useSuppliers } from '@/hooks/useSuppliers'
import { useUsage } from '@/hooks/useUsage'
import { useTreasury } from '@/hooks/useTreasury'
import { useAccounting } from '@/hooks/useAccounting'
import { useIncidents } from '@/hooks/useIncidents'

export function InvoicesPage() {
  const invoices = useInvoices()
  const usage = useUsage()
  const orders = useOrders()
  const suppliers = useSuppliers()
  const erp = useErpSnapshot()
  const treasury = useTreasury()
  const accounting = useAccounting()
  const incidents = useIncidents()
  return <InvoicesView {...invoices} usage={usage} suppliers={suppliers} orders={orders} erp={erp} treasury={treasury} accounting={accounting} incidents={incidents} />
}
