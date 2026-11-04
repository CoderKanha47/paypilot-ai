import type { TooltipPayload } from 'recharts'

const AXIS_STYLE = { fill: 'var(--color-muted)', fontSize: 11 } as const

interface ChartTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string | number
}

export function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-lg border border-navy-700/20 bg-navy-900 px-3 py-2 shadow-xl">
      {label ? <p className="mb-1 text-[11px] font-semibold text-muted">{String(label)}</p> : null}
      {payload.map((entry, index) => (
        <p key={index} className="text-xs tabular-nums text-ink">
          <span
            className="mr-1.5 inline-block h-2 w-2 rounded-full align-middle"
            style={{ backgroundColor: (entry as any).color || 'var(--color-accent)' }}
          />
          {(entry as any).name}: <span className="font-semibold">{String((entry as any).value)}</span>
        </p>
      ))}
    </div>
  )
}

export const tooltipStyles = {
  contentStyle: {
    background: 'var(--color-navy-900)',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 10,
    fontSize: 12,
    color: 'var(--color-ink)',
    padding: '8px 10px',
  },
  itemStyle: { color: 'var(--color-ink)' },
  labelStyle: { color: 'var(--color-muted)', fontSize: 11 },
}

export { AXIS_STYLE }