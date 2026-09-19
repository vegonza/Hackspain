import type { DiffLine } from '@/api/documents'

type Props = {
  lines: DiffLine[]
  label: string
}

export function MarkdownDiff({ lines, label }: Props) {
  return (
    <div className="diff-lines">
        <p className="px-4 pb-3 text-xs text-neutral-500">{label}</p>
        {lines.map((line, index) => (
          <div key={index} className="diff-line" data-kind={line.kind}>
            <span className="diff-number" aria-hidden="true">{line.before}</span>
            <span className="diff-number" aria-hidden="true">{line.after}</span>
            <span className="diff-sign">{line.kind === 'added' ? '+' : line.kind === 'removed' ? '−' : ' '}</span>
            <code>{line.text === '' ? '\u00a0' : line.spans.map((span, spanIndex) => (
              <span key={spanIndex} className={span.changed ? 'diff-change' : undefined}>{span.text}</span>
            ))}</code>
          </div>
        ))}
    </div>
  )
}
