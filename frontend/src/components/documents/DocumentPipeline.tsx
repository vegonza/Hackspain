import { Check, Circle, CircleAlert, LoaderCircle } from 'lucide-react'
import type { StageId } from '@/api/documents'
import type { useDocuments } from '@/hooks/useDocuments'

type Props = {
  totalCost: string
  totalLabel: string
  title: string
  stages: ReturnType<typeof useDocuments>['stages']
  selected: 'pdf' | StageId
  onSelect: (stage: StageId) => void
}

export function DocumentPipeline({ title, stages, selected, onSelect, totalCost, totalLabel }: Props) {
  return (
    <section className="document-pipeline" aria-label={title}>
      <header className="review-header"><h2>{title}</h2></header>
      <ol className="pipeline-stages">
        {stages.map(stage => (
          <li key={stage.id}>
            <button className="pipeline-stage" aria-pressed={selected === stage.id} onClick={() => onSelect(stage.id)}>
              <span className="pipeline-icon" data-status={stage.status}>
                {stage.status === 'ready' ? <Check size={14} aria-label={stage.statusLabel} />
                  : stage.status === 'processing' || stage.status === 'retrying' ? <LoaderCircle size={14} className="upload-spinner" />
                  : stage.status === 'error' ? <CircleAlert size={14} /> : <Circle size={14} />}
              </span>
              <span className="pipeline-stage-copy"><strong>{stage.label}</strong><span>{stage.description}</span></span>
              <span className="pipeline-status" aria-live="polite">{stage.status !== 'ready' && stage.status !== 'unavailable' && <span>{stage.statusLabel}</span>}{stage.durationLabel !== null && <span className="pipeline-duration">{stage.durationLabel}</span>}{stage.costLabel !== null && <span className="pipeline-cost">{stage.costLabel}</span>}</span>
            </button>
          </li>
        ))}
      </ol>
      <footer className="pipeline-total"><span>{totalLabel}</span><strong aria-live="polite">{totalCost}</strong></footer>
    </section>
  )
}
