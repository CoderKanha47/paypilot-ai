import { statusMeta } from '../lib/format'

export function StatusBadge({ status, size = 'md' }: { status: string; size?: 'sm' | 'md' }) {
  const meta = statusMeta(status)
  return (
    <span
      className={`tag ${meta.chip} ${size === 'sm' ? 'text-[10px] px-1.5' : ''}`}
      data-status={status}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} aria-hidden="true" />
      {meta.label}
    </span>
  )
}
