import { LoaderCircle } from 'lucide-react'

export function LoadingSpinner({ label }: { label: string }) {
  return (
    <div className="loading-spinner" role="status" aria-label={label}>
      <LoaderCircle size={28} className="animate-spin" aria-hidden="true" />
    </div>
  )
}
