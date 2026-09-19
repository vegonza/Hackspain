import type { DiffLine } from '@/api/documents'

type Props = {
  lines: DiffLine[]
  labels: { title: string; removed: string; added: string }
}

export function MarkdownDiff({ lines, labels }: Props) {
  return (
    <section className="markdown-diff" aria-label={labels.title}>
      <header className="diff-header">
        <span>{labels.title}</span>
        <span className="diff-legend"><span data-kind="removed">− {labels.removed}</span><span data-kind="added">+ {labels.added}</span></span>
      </header>
      <div className="diff-lines">
        {lines.map((line, index) => (
          <div key={index} className="diff-line" data-kind={line.kind}>
            <span className="diff-number" aria-hidden="true">{line.before}</span>
            <span className="diff-number" aria-hidden="true">{line.after}</span>
            <span className="diff-sign">{line.kind === 'added' ? '+' : line.kind === 'removed' ? '−' : ' '}</span>
            <code>{line.text || '\u00a0'}</code>
          </div>
        ))}
      </div>
    </section>
  )
}
