import type { DiffLine } from '@/api/documents'

type Props = {
  lines: DiffLine[]
}

export function MarkdownDiff({ lines }: Props) {
  return (
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
  )
}
