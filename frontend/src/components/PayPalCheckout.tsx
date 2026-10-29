import { useEffect, useRef, useState } from 'react'
import { ExternalLink, Loader2 } from 'lucide-react'

interface PayPalButtonInstance {
  render: (target: HTMLElement) => Promise<void>
  close?: () => void
}

interface PayPalSdkNamespace {
  Buttons: (options: Record<string, unknown>) => PayPalButtonInstance
}

const scriptPromises = new Map<string, Promise<void>>()

/** Load the official PayPal JavaScript SDK exactly once per client/currency. */
export function loadPaypalSdk(clientId: string, currency: string): Promise<void> {
  const src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=${encodeURIComponent(currency)}&intent=capture&components=buttons`
  const existing = scriptPromises.get(src)
  if (existing) return existing

  // Drop any previously injected SDK with different parameters.
  document
    .querySelectorAll<HTMLScriptElement>('script[data-paypilot-sdk="true"]')
    .forEach((node) => {
      if (node.src !== src) node.remove()
    })

  const promise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = src
    script.setAttribute('data-paypilot-sdk', 'true')
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => {
      scriptPromises.delete(src)
      reject(new Error('The PayPal JavaScript SDK could not be loaded. Check your network or client id.'))
    }
    document.body.appendChild(script)
  })

  scriptPromises.set(src, promise)
  return promise
}

interface PayPalCheckoutProps {
  orderId: string
  clientId: string
  currency: string
  amount: string
  description: string
  onApproved: (orderId: string) => Promise<void>
  onCancelled: () => Promise<void>
  onError: (message: string) => void
  disabled?: boolean
}

/**
 * Renders the official PayPal Sandbox button row for a server-created order.
 *
 * The order id is produced by the backend; after the payer approves in the
 * browser we hand control back to the backend, which captures and verifies
 * with PayPal. The client never reports a payment status of its own.
 */
export function PayPalCheckout({
  orderId,
  clientId,
  currency,
  amount,
  description,
  onApproved,
  onCancelled,
  onError,
  disabled = false,
}: PayPalCheckoutProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [sdkState, setSdkState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [sdkError, setSdkError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Latest callbacks in refs so the button instance never captures stale props.
  const approvedRef = useRef(onApproved)
  const cancelledRef = useRef(onCancelled)
  const errorRef = useRef(onError)
  approvedRef.current = onApproved
  cancelledRef.current = onCancelled
  errorRef.current = onError

  useEffect(() => {
    let disposed = false
    let buttons: PayPalButtonInstance | null = null
    setSdkState('loading')
    setSdkError(null)

    if (!clientId) {
      setSdkState('error')
      setSdkError('No PayPal client id is configured. Add Sandbox credentials in Settings.')
      return
    }

    loadPaypalSdk(clientId, currency)
      .then(() => {
        if (disposed || !containerRef.current) return
        const paypal = window.paypal as PayPalSdkNamespace | undefined
        if (!paypal) return
        buttons = paypal.Buttons({
          style: { layout: 'vertical', color: 'blue', shape: 'rect', label: 'pay', height: 46 },
          // Return the server-created order id: the backend owns the order.
          createOrder: () => orderId,
          onApprove: async (data: { orderID: string }) => {
            setSubmitting(true)
            try {
              await approvedRef.current(data.orderID)
            } finally {
              setSubmitting(false)
            }
          },
          onCancel: async () => {
            await cancelledRef.current()
          },
          onError: (cause: unknown) => {
            const message =
              cause instanceof Error
                ? cause.message
                : 'The PayPal button reported an error. Please try again.'
            errorRef.current(message)
          },
        })
        if (buttons && containerRef.current) {
          return buttons.render(containerRef.current)
        }
      })
      .then(() => {
        if (!disposed) setSdkState('ready')
      })
      .catch((cause: unknown) => {
        if (disposed) return
        setSdkState('error')
        setSdkError(cause instanceof Error ? cause.message : 'Could not initialise PayPal checkout.')
      })

    return () => {
      disposed = true
      try {
        buttons?.close?.()
      } catch {
        /* PayPal rejects an already-closed instance; nothing to do. */
      }
    }
  }, [orderId, clientId, currency])

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3 rounded-lg border border-white/8 bg-navy-900 px-3.5 py-2.5">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-ink">{description}</p>
          <p className="font-mono text-[11px] text-faint">Order {orderId}</p>
        </div>
        <p className="shrink-0 text-sm font-semibold tabular-nums text-ink">
          {amount} {currency}
        </p>
      </div>

      {sdkState === 'loading' ? (
        <div className="flex items-center justify-center gap-2 rounded-lg border border-white/8 bg-navy-900 py-8 text-sm text-muted">
          <Loader2 size={16} className="animate-spin text-accent-soft" aria-hidden="true" />
          Loading the PayPal checkout…
        </div>
      ) : null}

      {sdkState === 'error' ? (
        <div className="rounded-lg border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
          <p className="font-semibold">PayPal checkout unavailable</p>
          <p className="mt-1 text-xs leading-relaxed opacity-95">{sdkError}</p>
        </div>
      ) : null}

      <div
        ref={containerRef}
        className={sdkState === 'ready' && !disabled ? '' : 'pointer-events-none opacity-40'}
        aria-hidden={sdkState !== 'ready'}
      />

      {submitting ? (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted">
          <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          Verifying and recording the payment with PayPal…
        </div>
      ) : null}
    </div>
  )
}

/** Hosted checkout fallback — the same approval page PayPal hosts directly. */
export function HostedCheckoutLink({ href }: { href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-accent-soft hover:text-accent"
    >
      Open PayPal's hosted checkout instead <ExternalLink size={12} aria-hidden="true" />
    </a>
  )
}
