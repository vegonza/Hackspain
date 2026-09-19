import { ErpEntryDetails } from '@/components/erp/ErpEntryDetails'
import { ErpTable } from '@/components/erp/ErpTable'
import type { useErpSnapshot } from '@/hooks/useErpSnapshot'

export function ErpView(props: ReturnType<typeof useErpSnapshot>) {
  const { mount, loading, failed, selectedId, labels } = props
  return (
    <section className="documents-browser" ref={mount} aria-label={labels.title} aria-busy={loading}>
      {failed && <p role="alert" className="markdown-error">{labels.failed}</p>}
      {selectedId === null ? <ErpTable {...props} /> : <ErpEntryDetails {...props} />}
    </section>
  )
}
