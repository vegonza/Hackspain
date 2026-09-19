import { ErpEntryDetails } from '@/components/erp/ErpEntryDetails'
import { ErpTable } from '@/components/erp/ErpTable'
import type { useErpSnapshot } from '@/hooks/useErpSnapshot'

export function ErpView(props: ReturnType<typeof useErpSnapshot>) {
  const { mount, loading, selectedId, labels } = props
  return (
    <section className="invoices-browser" ref={mount} aria-label={labels.title} aria-busy={loading}>
      {selectedId === null ? <ErpTable {...props} /> : <ErpEntryDetails {...props} />}
    </section>
  )
}
