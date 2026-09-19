export function totalStageDuration(metrics: readonly { duration_ms: number | null }[]): number | null {
  const durations = metrics.map(metric => metric.duration_ms).filter(duration => duration !== null)
  return durations.length === 0 ? null : durations.reduce((total, duration) => total + duration, 0)
}
