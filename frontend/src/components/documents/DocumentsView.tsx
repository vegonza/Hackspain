import { FileText, DollarSign, Building2, Landmark, ShoppingCart } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DocumentsTable } from '@/components/documents/DocumentsTable'
import { DocumentDetails } from '@/components/documents/DocumentDetails'
import { ErpView } from '@/components/erp/ErpView'
import { UsageView } from '@/components/usage/UsageView'
import { OrdersView } from '@/components/orders/OrdersView'
import type { useOrders } from '@/hooks/useOrders'
import { SuppliersView } from '@/components/suppliers/SuppliersView'
import type { useErpSnapshot } from '@/hooks/useErpSnapshot'
import type { useSuppliers } from '@/hooks/useSuppliers'
import type { useUsage } from '@/hooks/useUsage'
import type { useDocuments } from '@/hooks/useDocuments'
import logo from '@/assets/logo.svg'

type Props = ReturnType<typeof useDocuments> & { usage: ReturnType<typeof useUsage>; suppliers: ReturnType<typeof useSuppliers>; orders: ReturnType<typeof useOrders>; erp: ReturnType<typeof useErpSnapshot> }

export function DocumentsView({ watchDocuments, labels, view, onNavigate, usage, suppliers, orders, erp, selectedId,
  sortColumn, sortDirection, onToggleSort, onUpload, filteredDocuments, documentsLoading, search, onSearch, onSelect,
  onDocumentLink, onDelete, deleting, mountDetail, documentName, selected, loading, extractionLoading,
  pdfUrl, pdfLoading, sourceTab, activeStage, emptyMessage, extractionLabels, canRetry, onRetrySelected,
  retrying, stageNavigation, metricsLoading, onSourceTab, erpRows, totalDuration, totalCost, featureAmounts,
  redoing, onRedo }: Props) {
  return (
    <div className="app-shell" ref={watchDocuments}>
      <main className="review-layout">
        <aside className="sidebar">
          <div className="sidebar-brand"><img className="brand-logo" src={logo} alt={labels.appName} /></div>
          <nav className="sidebar-navigation" aria-label={labels.appName}>
            <Button variant="sidebar" size="sidebar" className={`sidebar-link ${view === 'documents' ? 'bg-selected hover:bg-selected' : ''}`} asChild>
              <a href="/docs" onClick={onNavigate} aria-current={view === 'documents' ? 'page' : undefined}><FileText /><span>{labels.library}</span></a>
            </Button>
            <Button variant="sidebar" size="sidebar" className={`sidebar-link ${view === 'suppliers' ? 'bg-selected hover:bg-selected' : ''}`} asChild>
              <a href="/suppliers" onClick={onNavigate} aria-current={view === 'suppliers' ? 'page' : undefined}><Building2 /><span>{suppliers.labels.title}</span></a>
            </Button>
            <Button variant="sidebar" size="sidebar" className={`sidebar-link ${view === 'orders' ? 'bg-selected hover:bg-selected' : ''}`} asChild>
              <a href="/orders" onClick={onNavigate} aria-current={view === 'orders' ? 'page' : undefined}><ShoppingCart /><span>{orders.labels.title}</span></a>
            </Button>
            <Button variant="sidebar" size="sidebar" className={`sidebar-link ${view === 'erp' ? 'bg-selected hover:bg-selected' : ''}`} asChild>
              <a href="/erp" onClick={onNavigate} aria-current={view === 'erp' ? 'page' : undefined}><Landmark /><span>{labels.erp}</span></a>
            </Button>
            <Button variant="sidebar" size="sidebar" className={`sidebar-link ${view === 'usage' ? 'bg-selected hover:bg-selected' : ''}`} asChild>
              <a href="/cost" onClick={onNavigate} aria-current={view === 'usage' ? 'page' : undefined}><DollarSign /><span>{labels.usage}</span></a>
            </Button>
          </nav>
        </aside>
        {view === 'usage' ? <UsageView {...usage} />
          : view === 'orders' ? <OrdersView {...orders} />
          : view === 'suppliers' ? <SuppliersView {...suppliers} />
          : view === 'erp' ? <ErpView {...erp} />
          : view === 'not-found' ? <section className="stage-empty"><h1>{labels.notFound}</h1><Button variant="link" asChild><a href="/docs" onClick={onNavigate}>{labels.library}</a></Button></section>
          : selectedId !== null ? <DocumentDetails mountDetail={mountDetail} documentName={documentName} selectedId={selectedId}
            selected={selected} featureAmounts={featureAmounts} loading={loading} extractionLoading={extractionLoading} pdfUrl={pdfUrl} pdfLoading={pdfLoading}
            sourceTab={sourceTab} activeStage={activeStage} emptyMessage={emptyMessage} labels={labels} extractionLabels={extractionLabels}
            canRetry={canRetry} onRetrySelected={onRetrySelected} retrying={retrying} stageNavigation={stageNavigation} metricsLoading={metricsLoading}
            onNavigate={onNavigate} onSourceTab={onSourceTab} erpRows={erpRows} totalDuration={totalDuration} totalCost={totalCost} />
          : <DocumentsTable sortColumn={sortColumn} sortDirection={sortDirection} onToggleSort={onToggleSort}
            onUpload={onUpload} rows={filteredDocuments} documentsLoading={documentsLoading} search={search} onSearch={onSearch}
            onSelect={onSelect} onDocumentLink={onDocumentLink} onDelete={onDelete} deleting={deleting} labels={labels}
            onRedo={onRedo} redoDisabled={redoing || retrying || deleting} />}
      </main>
    </div>
  )
}
