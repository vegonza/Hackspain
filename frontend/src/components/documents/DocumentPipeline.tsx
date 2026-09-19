import { FileText, Text, ScanText, ListChecks, Landmark } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { StageId } from '@/api/documents'
import type { useDocuments } from '@/hooks/useDocuments'

const stageIcons = { text: Text, ocr: ScanText, extraction: ListChecks } satisfies Record<StageId, typeof Text>

type Props = Pick<ReturnType<typeof useDocuments>, 'stageNavigation' | 'metricsLoading' | 'sourceTab' | 'onSourceTab'> & {
  label: string
  pdfLabel: string
  erpLabel: string
}

export function DocumentPipeline({ stageNavigation, metricsLoading, sourceTab, onSourceTab, label, pdfLabel, erpLabel }: Props) {
  return (
    <nav className="sidebar-navigation document-navigation" aria-label={label}>
      <Button variant="sidebar" size="sidebar" className={`sidebar-link ${sourceTab === 'pdf' ? 'bg-selected hover:bg-selected' : ''}`} aria-current={sourceTab === 'pdf' ? 'page' : undefined} onClick={() => onSourceTab('pdf')}>
        <FileText /><span>{pdfLabel}</span>
      </Button>
      {stageNavigation.map(stage => {
        const Icon = stageIcons[stage.id]
        return <Button key={stage.id} variant="sidebar" size="sidebar" className={`sidebar-link ${sourceTab === stage.id ? 'bg-selected hover:bg-selected' : ''}`} aria-current={sourceTab === stage.id ? 'page' : undefined} onClick={() => onSourceTab(stage.id)}>
          <Icon /><span>{stage.label}</span>
          <span className="document-stage-metrics" aria-busy={metricsLoading}>
            {metricsLoading ? <Skeleton className="h-3 w-10" /> : stage.durationLabel !== null && <span>{stage.durationLabel}</span>}
            {metricsLoading ? <Skeleton className="h-3 w-12" /> : <span>{stage.costLabel}</span>}
          </span>
        </Button>
      })}
      <Button variant="sidebar" size="sidebar" className={`sidebar-link ${sourceTab === 'erp' ? 'bg-selected hover:bg-selected' : ''}`} aria-current={sourceTab === 'erp' ? 'page' : undefined} onClick={() => onSourceTab('erp')}>
        <Landmark /><span>{erpLabel}</span>
      </Button>
    </nav>
  )
}
