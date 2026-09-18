import { ExampleSkeleton } from './ExampleSkeleton'

interface ExampleViewProps {
  appName: string
  title: string
  description: string
  buttonLabel: string
  loadingLabel: string
  message: string
  isLoading: boolean
  onConnect: () => Promise<void>
}

export function ExampleView({
  appName, title, description, buttonLabel, loadingLabel, message, isLoading, onConnect,
}: ExampleViewProps) {
  return (
    <main className="grid min-h-svh place-items-center p-6">
      <section className="w-full max-w-md rounded-xl border border-border bg-white p-8 shadow-sm">
        <p className="mb-6 text-sm font-medium text-neutral-500">{appName}</p>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm text-neutral-600">{description}</p>
        <button
          type="button"
          disabled={isLoading}
          onClick={onConnect}
          className="mt-6 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900 disabled:cursor-wait disabled:opacity-50"
        >
          {buttonLabel}
        </button>
        <div className="mt-5 min-h-6" aria-live="polite" aria-busy={isLoading}>
          {isLoading
            ? <ExampleSkeleton label={loadingLabel} />
            : <p className="text-sm text-emerald-700">{message}</p>}
        </div>
      </section>
    </main>
  )
}
