import { Skeleton } from '@/components/ui/skeleton'

interface ExampleSkeletonProps {
  label: string
}

export function ExampleSkeleton({ label }: ExampleSkeletonProps) {
  return (
    <div role="status">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-5 w-64 max-w-full" aria-hidden="true" />
    </div>
  )
}
