import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

interface StatCardProps {
  label: string
  value: string
  hint?: ReactNode
  icon: LucideIcon
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'accent'
}

const TONES: Record<string, string> = {
  default: 'text-accent-soft bg-accent/12 border-accent/25',
  success: 'text-success bg-success/12 border-success/25',
  warning: 'text-warning bg-warning/12 border-warning/25',
  danger: 'text-danger bg-danger/12 border-danger/25',
  accent: 'text-info bg-info/12 border-info/25',
}

export function StatCard({ label, value, hint, icon: Icon, tone = 'default' }: StatCardProps) {
  return (
    <div className="card-raised p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.09em] text-faint">{label}</p>
          <p className="mt-2 truncate text-2xl font-semibold tabular-nums text-ink">{value}</p>
        </div>
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg border ${TONES[tone]}`}>
          <Icon size={17} aria-hidden="true" />
        </span>
      </div>
      {hint ? <div className="mt-2 text-xs text-muted">{hint}</div> : null}
    </div>
  )
}
