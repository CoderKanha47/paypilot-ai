/** Formatting helpers. Amounts arrive as exact decimal strings from the API —
 * they are never parsed into floats for display. */

import type { TxStatus } from './types'

const ZERO_DECIMAL = new Set(['JPY', 'KRW', 'VND', 'CLP', 'ISK', 'HUF', 'TWD'])

export function money(amount: string | number | null | undefined, currency = 'USD'): string {
  if (amount === null || amount === undefined || amount === '') return '—'
  const numeric = typeof amount === 'number' ? amount.toFixed(2) : amount
  const digits = ZERO_DECIMAL.has(currency.toUpperCase()) ? 0 : 2
  const [whole, fraction = ''] = String(numeric).split('.')
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const padded = digits === 0 ? '' : `.${(fraction + '00').slice(0, digits)}`
  return `${grouped}${padded} ${currency}`
}

export function moneyShort(amount: string | number | null | undefined, currency = 'USD'): string {
  if (amount === null || amount === undefined || amount === '') return '—'
  const digits = ZERO_DECIMAL.has(currency.toUpperCase()) ? 0 : 2
  const value = typeof amount === 'number' ? amount.toFixed(digits) : amount
  const [whole, fraction = ''] = String(value).split('.')
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return digits === 0 ? grouped : `${grouped}.${(fraction + '00').slice(0, digits)}`
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value.endsWith('Z') || value.includes('+') ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value.endsWith('Z') || value.includes('+') ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value.endsWith('Z') || value.includes('+') ? value : `${value}Z`)
  const diffMs = Date.now() - date.getTime()
  const minutes = Math.round(diffMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  return formatDate(value)
}

export const STATUS_META: Record<
  TxStatus,
  { label: string; dot: string; chip: string }
> = {
  completed: {
    label: 'Completed',
    dot: 'bg-success',
    chip: 'text-success bg-success/12 border border-success/25',
  },
  pending: {
    label: 'Pending',
    dot: 'bg-warning',
    chip: 'text-warning bg-warning/12 border border-warning/25',
  },
  failed: {
    label: 'Failed',
    dot: 'bg-danger',
    chip: 'text-danger bg-danger/12 border border-danger/25',
  },
  declined: {
    label: 'Declined',
    dot: 'bg-danger',
    chip: 'text-danger bg-danger/12 border border-danger/25',
  },
  cancelled: {
    label: 'Cancelled',
    dot: 'bg-faint',
    chip: 'text-muted bg-white/6 border border-white/12',
  },
  expired: {
    label: 'Expired',
    dot: 'bg-faint',
    chip: 'text-muted bg-white/6 border border-white/12',
  },
  refunded: {
    label: 'Refunded',
    dot: 'bg-info',
    chip: 'text-info bg-info/12 border border-info/25',
  },
}

export function statusMeta(status: string) {
  return (
    STATUS_META[status as TxStatus] ?? {
      label: status.charAt(0).toUpperCase() + status.slice(1),
      dot: 'bg-muted',
      chip: 'text-muted bg-white/6 border border-white/12',
    }
  )
}

export function truncate(value: string, max = 48): string {
  if (value.length <= max) return value
  return `${value.slice(0, max - 1)}…`
}

export function initialsOf(value: string): string {
  const parts = value.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'PP'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}
