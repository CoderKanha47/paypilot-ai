import type { TooltipPayload } from 'recharts'

const AXIS_STYLE = { fill: '#6b769a', fontSize: 11 } as const

interface ChartTooltipProps {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string | number
}

export function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-lg border border-white/12 bg-navy-900 px-3 py-2 shadow-xl">
      {label ? <p className="mb-1 text-[11px] font-semibold text-muted">{String(label)}</p> : null}
      {payload.map((entry, index) => (
        <p key={index} className="text-xs tabular-nums text-ink">
          <span
            className="mr-1.5 inline-block h-2 w-2 rounded-full align-middle"
            style={{ backgroundColor: (entry as any).color || '#7c5cff' }}
          />
          {(entry as any).name}: <span className="font-semibold">{String((entry as any).value)}</span>
        </p>
      ))}
    </div>
  )
}

export const tooltipStyles = {
  contentStyle: {
    background: '#080c18',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 10,
    fontSize: 12,
    color: '#e8ecf9',
    padding: '8px 10px',
  },
  itemStyle: { color: '#e8ecf9' },
  labelStyle: { color: '#98a2c0', fontSize: 11 },
}

export { AXIS_STYLE }