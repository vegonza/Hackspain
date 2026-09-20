import type { IssuedInvoice } from '@/api/issued'
import { IssuedInvoiceEditor } from '@/components/issued/IssuedInvoiceEditor'
import { useIssuedEditor } from '@/hooks/useIssuedEditor'

type Props = { id: string; onUpdated: (invoice: IssuedInvoice) => void }
export function IssuedInvoicePage({ id, onUpdated }: Props) {
  const editor = useIssuedEditor(id, onUpdated)
  return <IssuedInvoiceEditor editor={editor} />
}
