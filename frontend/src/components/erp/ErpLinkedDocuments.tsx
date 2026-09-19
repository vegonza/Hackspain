import { FileText } from 'lucide-react'
import type { MouseEvent } from 'react'
import { Skeleton } from '@/components/ui/skeleton'

type Props = {
  title: string
  empty: string
  loading: boolean
  documents: { id: string; name: string; href: string }[]
  onNavigate: (event: MouseEvent<HTMLAnchorElement>) => void
}

export function ErpLinkedDocuments({ title, empty, loading, documents, onNavigate }: Props) {
  return (
    <section className="document-data" aria-label={title} aria-busy={loading}>
      <header className="review-header"><h2>{title}</h2></header>
      {loading ? <Skeleton className="h-4 w-64" />
        : documents.length === 0 ? <p className="text-sm text-muted-foreground">{empty}</p>
        : <ul className="divide-y border-y">
          {documents.map(document => <li key={document.id}>
            <a className="flex items-center gap-2 py-3 text-sm font-medium hover:underline" href={document.href} onClick={onNavigate}>
              <FileText size={14} className="shrink-0 text-muted-foreground" /><span className="truncate">{document.name}</span>
            </a>
          </li>)}
        </ul>}
    </section>
  )
}
