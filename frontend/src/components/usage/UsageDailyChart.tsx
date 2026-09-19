import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { UsageDailyTooltip } from '@/components/usage/UsageDailyTooltip'
import type { useUsage } from '@/hooks/useUsage'

type Props = Pick<ReturnType<typeof useUsage>, 'daily' | 'loading' | 'labels'>

export function UsageDailyChart({ daily, loading, labels }: Props) {
  return <section className="usage-chart">
    <div className="usage-chart-canvas">
      {loading ? <Skeleton className="h-full w-full" /> : daily.length === 0 ? <p>{labels.empty}</p> : (
        <ResponsiveContainer width="100%" height="100%" minHeight={192}>
          <BarChart data={daily} margin={{ top: 8, right: 4, bottom: 0, left: 8 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="date" tickLine={false} axisLine={false} tickMargin={8} minTickGap={24}
              tickFormatter={date => new Date(`${date}T00:00:00`).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })} />
            <YAxis width="auto" tickLine={false} axisLine={false} tickMargin={8} />
            <Tooltip cursor={false} content={<UsageDailyTooltip costLabel={labels.totalCost} />} isAnimationActive={false} />
            <Bar dataKey="cost" fill="var(--primary)" radius={0} maxBarSize={32} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  </section>
}
