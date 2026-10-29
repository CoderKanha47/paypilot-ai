import { AlertTriangle, Info, RefreshCw, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'

interface ErrorBannerProps {
  title?: string
  message: string
  errors?: string[]
  onRetry?: () => void
  tone?: 'danger' | 'warning'
  children?: ReactNode
}

export function ErrorBanner({
  title = 'Something went wrong',
  message,
  errors = [],
  onRetry,
  tone = 'danger',
  children,
}: ErrorBannerProps) {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  const palette =
    tone === 'warning'
      ? 'border-warning/30 bg-warning/8 text-warning'
      : 'border-danger/30 bg-danger/8 text-danger'
  const Icon = tone === 'warning' ? Info : AlertTriangle

  return (
    <div className={`rounded-lg border ${palette} p-4`} role="alert">
      <div className="flex items-start gap-3">
        <Icon size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">{title}</p>
          <p className="mt-1 break-words text-sm leading-relaxed opacity-95">{message}</p>
          {errors.length > 0 ? (
            <ul className="mt-2 space-y-1 text-xs opacity-90">
              {errors.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          ) : null}
          {children}
          {onRetry ? (
            <button type="button" className="btn btn-ghost mt-3 text-xs" onClick={onRetry}>
              <RefreshCw size={13} aria-hidden="true" /> Try again
            </button>
          ) : null}
        </div>
        <button
          type="button"
          className="rounded p-1 opacity-70 transition hover:opacity-100"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss error"
        >
          <X size={15} aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
