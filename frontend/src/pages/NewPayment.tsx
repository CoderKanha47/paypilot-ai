import { useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle2,
  CirclePlus,
  Clock3,
  ExternalLink,
  Info,
  Loader2,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  XOctagon,
} from 'lucide-react'
import { useApp } from '../context/AppContext'
import { api, ApiError, errorMessage } from '../lib/api'
import { money } from '../lib/format'
import type { CaptureOrderResponse, CreateOrderResponse, TxStatus } from '../lib/types'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { HostedCheckoutLink, PayPalCheckout } from '../components/PayPalCheckout'
import { StatusBadge } from '../components/StatusBadge'

type Phase =
  | 'form'
  | 'creating'
  | 'awaiting'
  | 'capturing'
  | 'success'
  | 'declined'
  | 'failed'
  | 'pending'
  | 'cancelled'

interface FormState {
  amount: string
  currency: string
  description: string
  customer_reference: string
}

const EMPTY: FormState = {
  amount: '',
  currency: 'USD',
  description: '',
  customer_reference: '',
}

const STEPS = [
  { label: 'Order created', hint: 'Server calls the PayPal Orders API' },
  { label: 'Payer approves', hint: 'PayPal Sandbox checkout' },
  { label: 'Captured & verified', hint: 'Server captures and stores the record' },
]

function stepIndex(phase: Phase): number {
  if (phase === 'form' || phase === 'creating') return 0
  if (phase === 'awaiting') return 1
  return 2
}

export function NewPayment() {
  const { config, demoMode, reload } = useApp()
  const [form, setForm] = useState<FormState>({
    ...EMPTY,
    currency: config?.paypal.currency ?? 'USD',
  })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [phase, setPhase] = useState<Phase>('form')
  const [order, setOrder] = useState<CreateOrderResponse | null>(null)
  const [result, setResult] = useState<CaptureOrderResponse | null>(null)
  const [actionError, setActionError] = useState<{ message: string; errors?: string[] } | null>(null)

  const currencies = config?.supported_currencies ?? ['USD']
  const active = stepIndex(phase)
  const busy = phase === 'creating' || phase === 'capturing'

  const validate = (): boolean => {
    const errors: Record<string, string> = {}
    const raw = form.amount.trim()
    if (!raw) errors.amount = 'Enter an amount.'
    else if (!/^\d{1,10}([.,]\d{1,2})?$/.test(raw))
      errors.amount = 'Use a number like 149.99 (max 2 decimals).'
    else if (Number(raw.replace(',', '.')) <= 0) errors.amount = 'Amount must be greater than zero.'

    if (!form.description.trim()) errors.description = 'Describe what this payment is for.'
    else if (form.description.trim().length > 250) errors.description = 'Keep it under 250 characters.'

    if (form.customer_reference.length > 120)
      errors.customer_reference = 'Keep the reference under 120 characters.'

    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const reset = () => {
    setForm({ ...EMPTY, currency: form.currency })
    setOrder(null)
    setResult(null)
    setActionError(null)
    setFieldErrors({})
    setPhase('form')
  }

  const createOrder = async (event: FormEvent) => {
    event.preventDefault()
    setActionError(null)
    if (!validate()) return

    setPhase('creating')
    try {
      const created = await api.post<CreateOrderResponse>('/api/payments/create-order', {
        amount: form.amount.replace(',', '.'),
        currency: form.currency,
        description: form.description.trim(),
        customer_reference: form.customer_reference.trim() || null,
      })
      setOrder(created)
      setPhase('awaiting')
    } catch (cause) {
      setPhase('form')
      if (cause instanceof ApiError) {
        setActionError({ message: cause.message, errors: cause.errors })
      } else {
        setActionError({ message: errorMessage(cause) })
      }
    }
  }

  const setResultState = (status: TxStatus) => {
    if (status === 'completed') setPhase('success')
    else if (status === 'declined') setPhase('declined')
    else if (status === 'failed') setPhase('failed')
    else setPhase('pending')
  }

  const capture = async (orderId: string, demoOutcome?: 'approve' | 'decline' | 'fail') => {
    if (!order) return
    setActionError(null)
    setPhase('capturing')
    try {
      const captured = await api.post<CaptureOrderResponse>('/api/payments/capture-order', {
        order_id: orderId,
        transaction_id: order.transaction_id,
        ...(demoOutcome ? { demo_outcome: demoOutcome } : {}),
      })
      setResult(captured)
      reload()
      setResultState(captured.transaction.status)
    } catch (cause) {
      setPhase('awaiting')
      if (cause instanceof ApiError) {
        setActionError({ message: cause.message, errors: cause.errors })
      } else {
        setActionError({ message: errorMessage(cause) })
      }
    }
  }

  const cancel = async () => {
    if (!order) return
    setActionError(null)
    try {
      await api.post<CaptureOrderResponse>('/api/payments/cancel-order', {
        order_id: order.order_id,
        transaction_id: order.transaction_id,
      })
      setPhase('cancelled')
      reload()
    } catch (cause) {
      setActionError({ message: errorMessage(cause) })
    }
  }

  const summaryAmount = useMemo(
    () => (form.amount ? money(form.amount.replace(',', '.'), form.currency) : '—'),
    [form.amount, form.currency],
  )

  return (
    <>
      <PageHeader
        title="New payment"
        description="Create a PayPal Sandbox order, let the payer approve it, then capture it server-side."
        badge={
          <span
            className={`tag ${
              demoMode
                ? 'border border-warning/35 bg-warning/12 text-warning'
                : 'border border-success/30 bg-success/12 text-success'
            }`}
          >
            {demoMode ? 'DEMO CHECKOUT' : 'SANDBOX CHECKOUT'}
          </span>
        }
        actions={
          phase !== 'form' ? (
            <button type="button" className="btn btn-ghost" onClick={reset}>
              <ArrowLeft size={15} aria-hidden="true" /> Start over
            </button>
          ) : undefined
        }
      />

      {/* ------------------------------------------------------------ steps */}
      <ol className="mb-6 grid grid-cols-1 gap-2 sm:grid-cols-3">
        {STEPS.map((step, index) => {
          const state = index < active ? 'done' : index === active ? 'current' : 'todo'
          return (
            <li
              key={step.label}
              className={`flex items-center gap-3 rounded-lg border px-3.5 py-2.5 text-sm ${
                state === 'current'
                  ? 'border-accent/40 bg-accent/8'
                  : state === 'done'
                    ? 'border-success/25 bg-success/8'
                    : 'border-white/8 bg-navy-850'
              }`}
            >
              <span
                className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold ${
                  state === 'done'
                    ? 'bg-success/20 text-success'
                    : state === 'current'
                      ? 'bg-accent text-white'
                      : 'bg-white/8 text-faint'
                }`}
              >
                {state === 'done' ? <CheckCircle2 size={13} aria-hidden="true" /> : index + 1}
              </span>
              <span className="min-w-0">
                <span
                  className={`block truncate font-medium ${state === 'todo' ? 'text-muted' : 'text-ink'}`}
                >
                  {step.label}
                </span>
                <span className="block truncate text-[11px] text-faint">{step.hint}</span>
              </span>
            </li>
          )
        })}
      </ol>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* ------------------------------------------------------- main card */}
        <div className="lg:col-span-2">
          {actionError ? (
            <div className="mb-4">
              <ErrorBanner
                title="Payment step failed"
                message={actionError.message}
                errors={actionError.errors}
              />
            </div>
          ) : null}

          {phase === 'form' || phase === 'creating' ? (
            <form className="card p-5 sm:p-6" onSubmit={createOrder} noValidate>
              <h2 className="text-sm font-semibold text-ink">Payment details</h2>

              <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-[180px_1fr]">
                <div>
                  <label htmlFor="currency" className="mb-1.5 block text-xs font-medium text-muted">
                    Currency
                  </label>
                  <select
                    id="currency"
                    className="input"
                    value={form.currency}
                    onChange={(event) => setForm({ ...form, currency: event.target.value })}
                    disabled={busy}
                  >
                    {currencies.map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="amount" className="mb-1.5 block text-xs font-medium text-muted">
                    Amount
                  </label>
                  <div className="relative">
                    <input
                      id="amount"
                      className={`input pr-16 tabular-nums ${fieldErrors.amount ? 'input-error' : ''}`}
                      inputMode="decimal"
                      placeholder="149.99"
                      value={form.amount}
                      onChange={(event) => setForm({ ...form, amount: event.target.value })}
                      disabled={busy}
                      aria-invalid={Boolean(fieldErrors.amount)}
                      aria-describedby={fieldErrors.amount ? 'amount-error' : undefined}
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-faint">
                      {form.currency}
                    </span>
                  </div>
                  {fieldErrors.amount ? (
                    <p id="amount-error" className="mt-1.5 text-xs text-danger">
                      {fieldErrors.amount}
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="mt-4">
                <label htmlFor="description" className="mb-1.5 block text-xs font-medium text-muted">
                  Description
                </label>
                <input
                  id="description"
                  className={`input ${fieldErrors.description ? 'input-error' : ''}`}
                  placeholder="Brand identity package — Northwind Studio"
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                  maxLength={250}
                  disabled={busy}
                  aria-invalid={Boolean(fieldErrors.description)}
                />
                <div className="mt-1.5 flex items-start justify-between gap-3">
                  <p className={`text-xs ${fieldErrors.description ? 'text-danger' : 'text-faint'}`}>
                    {fieldErrors.description ?? 'Shown to the payer during checkout.'}
                  </p>
                  <span className="shrink-0 text-[11px] tabular-nums text-faint">
                    {form.description.length}/250
                  </span>
                </div>
              </div>

              <div className="mt-4">
                <label
                  htmlFor="reference"
                  className="mb-1.5 block text-xs font-medium text-muted"
                >
                  Customer reference <span className="text-faint">(optional)</span>
                </label>
                <input
                  id="reference"
                  className={`input font-mono text-[13px] ${fieldErrors.customer_reference ? 'input-error' : ''}`}
                  placeholder="INV-2026-014"
                  value={form.customer_reference}
                  onChange={(event) => setForm({ ...form, customer_reference: event.target.value })}
                  maxLength={120}
                  disabled={busy}
                />
                {fieldErrors.customer_reference ? (
                  <p className="mt-1.5 text-xs text-danger">{fieldErrors.customer_reference}</p>
                ) : (
                  <p className="mt-1.5 text-xs text-faint">
                    Passed to PayPal as <code className="font-mono">custom_id</code> and{' '}
                    <code className="font-mono">invoice_id</code> for reconciliation.
                  </p>
                )}
              </div>

              <div className="mt-6 flex flex-col gap-3 border-t border-white/8 pt-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.09em] text-faint">You will charge</p>
                  <p className="text-xl font-semibold tabular-nums text-ink">{summaryAmount}</p>
                </div>
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <CirclePlus size={16} aria-hidden="true" />}
                  {busy ? 'Creating PayPal order…' : 'Create PayPal order'}
                </button>
              </div>
            </form>
          ) : null}

          {phase === 'awaiting' || phase === 'capturing' ? (
            <div className="card p-5 sm:p-6">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-ink">Approve the payment</h2>
                  <p className="mt-1 text-xs leading-relaxed text-muted">
                    The order now exists on PayPal. Approve it to continue — the app will capture and
                    verify it on the server.
                  </p>
                </div>
                <StatusBadge status={order?.status ?? 'pending'} />
              </div>

              {demoMode ? (
                <DemoApprovalPanel
                  pending={phase === 'capturing'}
                  onOutcome={(outcome) => capture(order!.order_id, outcome)}
                  onCancel={cancel}
                />
              ) : order ? (
                <>
                  <PayPalCheckout
                    orderId={order.order_id}
                    clientId={order.paypal_client_id}
                    currency={order.sdk_currency}
                    amount={money(order.amount, order.currency)}
                    description={order.description}
                    disabled={phase === 'capturing'}
                    onApproved={(orderId) => capture(orderId)}
                    onCancelled={cancel}
                    onError={(message) => {
                      setActionError({ message })
                    }}
                  />
                  {order.approve_link || order.approval_url ? (
                    <HostedCheckoutLink href={order.approve_link ?? order.approval_url ?? ''} />
                  ) : null}
                </>
              ) : null}

              {order?.notice ? (
                <p className="mt-4 rounded-lg border border-warning/25 bg-warning/8 p-3 text-xs leading-relaxed text-warning">
                  {order.notice}
                </p>
              ) : null}

              <button type="button" className="btn btn-ghost mt-4" onClick={cancel}>
                Cancel this request
              </button>
            </div>
          ) : null}

          {phase === 'success' && result ? (
            <OutcomePanel
              tone="success"
              icon={CheckCircle2}
              title="Payment captured"
              body={`${money(result.transaction.amount, result.transaction.currency)} was captured and recorded.`}
              transaction={result.transaction}
              alreadyCaptured={result.already_captured}
              onReset={reset}
            />
          ) : null}

          {phase === 'declined' && result ? (
            <OutcomePanel
              tone="danger"
              icon={ThumbsDown}
              title="Payment declined"
              body={
                result.transaction.failure_reason ??
                'PayPal declined this payment. No money moved.'
              }
              transaction={result.transaction}
              alreadyCaptured={false}
              onReset={reset}
            />
          ) : null}

          {phase === 'failed' && result ? (
            <OutcomePanel
              tone="danger"
              icon={XOctagon}
              title="Capture failed"
              body={
                result.transaction.failure_reason ??
                'PayPal returned a FAILED status. No money was collected.'
              }
              transaction={result.transaction}
              alreadyCaptured={false}
              onReset={reset}
            />
          ) : null}

          {phase === 'pending' && result ? (
            <OutcomePanel
              tone="warning"
              icon={Clock3}
              title="Payment pending"
              body="PayPal has not settled this payment yet. It will move to Completed once asynchronous review finishes."
              transaction={result.transaction}
              alreadyCaptured={false}
              onReset={reset}
            />
          ) : null}

          {phase === 'cancelled' ? (
            <div className="card p-6 text-center">
              <span className="mx-auto grid h-12 w-12 place-items-center rounded-xl border border-white/12 bg-white/5 text-muted">
                <ArrowLeft size={22} aria-hidden="true" />
              </span>
              <h2 className="mt-4 text-base font-semibold text-ink">Payment request cancelled</h2>
              <p className="mx-auto mt-1.5 max-w-md text-sm leading-relaxed text-muted">
                The order was cancelled before approval, so nothing was charged. You can create a new
                request whenever you are ready.
              </p>
              <button type="button" className="btn btn-primary mt-5" onClick={reset}>
                Create another payment
              </button>
            </div>
          ) : null}
        </div>

        {/* ------------------------------------------------------- side rail */}
        <aside className="space-y-4">
          <div className="card p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <ShieldCheck size={14} className="text-success" aria-hidden="true" />
              How this works
            </div>
            <ol className="mt-3 space-y-3 text-xs leading-relaxed text-muted">
              <li className="flex gap-2">
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                Your backend creates the order with{' '}
                <code className="font-mono text-[11px]">POST /v2/checkout/orders</code>.
              </li>
              <li className="flex gap-2">
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                The payer approves inside PayPal's own hosted experience.
              </li>
              <li className="flex gap-2">
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                The backend captures the order and re-checks the amount, currency and status before
                writing a record.
              </li>
              <li className="flex gap-2">
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                Nothing the browser reports is trusted on its own.
              </li>
            </ol>
          </div>

          <div className="card p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <Info size={14} className="text-accent-soft" aria-hidden="true" />
              Current mode
            </div>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              {demoMode
                ? 'PayPal credentials are missing, so this run uses the labelled demo engine. Results are simulated locally and are NOT Sandbox transactions.'
                : `Connected to PayPal ${config?.paypal.mode === 'sandbox' ? 'Sandbox (api-m.sandbox.paypal.com)' : 'live'} with public client id ${config?.paypal.client_id.slice(0, 14)}…`}
            </p>
            {demoMode ? (
              <Link to="/settings" className="btn btn-ghost mt-3 w-full text-xs">
                Configure PayPal <ExternalLink size={13} aria-hidden="true" />
              </Link>
            ) : null}
          </div>

          <div className="card p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <ThumbsUp size={14} className="text-warning" aria-hidden="true" />
              Sandbox test cards
            </div>
            <ul className="mt-2 space-y-1.5 text-[11px] leading-relaxed text-muted">
              <li>
                Approve:{' '}
                <code className="font-mono text-faint">4111 1111 1111 1111</code> — any future date.
              </li>
              <li>Decline: <code className="font-mono text-faint">4000 0000 0000 0002</code></li>
              <li>Insufficient funds: <code className="font-mono text-faint">4000 0000 0000 9995</code></li>
            </ul>
          </div>
        </aside>
      </div>
    </>
  )
}

/* ------------------------------------------------------------------ panels */

function DemoApprovalPanel({
  pending,
  onOutcome,
  onCancel,
}: {
  pending: boolean
  onOutcome: (outcome: 'approve' | 'decline' | 'fail') => void
  onCancel: () => void
}) {
  return (
    <div className="rounded-xl border border-warning/35 bg-warning/8 p-4">
      <div className="flex items-start gap-2.5">
        <Info size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold uppercase tracking-[0.09em] text-warning">
            Demo approval — not a PayPal transaction
          </p>
          <p className="mt-1.5 text-xs leading-relaxed text-warning/90">
            No PayPal credentials are configured, so no order exists on PayPal. The buttons below
            simulate the payer's decision locally so you can explore the interface. They must never be
            described as Sandbox activity.
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-primary"
              disabled={pending}
              onClick={() => onOutcome('approve')}
            >
              <ThumbsUp size={15} aria-hidden="true" /> Simulate approval
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={pending}
              onClick={() => onOutcome('decline')}
            >
              <ThumbsDown size={15} aria-hidden="true" /> Simulate decline
            </button>
            <button
              type="button"
              className="btn btn-danger"
              disabled={pending}
              onClick={() => onOutcome('fail')}
            >
              <XOctagon size={15} aria-hidden="true" /> Simulate failure
            </button>
            <button type="button" className="btn btn-ghost" disabled={pending} onClick={onCancel}>
              Cancel
            </button>
          </div>

          {pending ? (
            <p className="mt-3 flex items-center gap-2 text-xs text-muted">
              <Loader2 size={13} className="animate-spin" aria-hidden="true" /> Recording the simulated
              result…
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function OutcomePanel({
  tone,
  icon: Icon,
  title,
  body,
  transaction,
  alreadyCaptured,
  onReset,
}: {
  tone: 'success' | 'danger' | 'warning'
  icon: typeof CheckCircle2
  title: string
  body: string
  transaction: CaptureOrderResponse['transaction']
  alreadyCaptured: boolean
  onReset: () => void
}) {
  const palette =
    tone === 'success'
      ? 'border-success/30 bg-success/8 text-success'
      : tone === 'warning'
        ? 'border-warning/30 bg-warning/8 text-warning'
        : 'border-danger/30 bg-danger/8 text-danger'

  return (
    <div className="card overflow-hidden">
      <div className={`flex items-start gap-3 border-b px-5 py-4 ${palette}`}>
        <Icon size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">{title}</h2>
          <p className="mt-1 text-xs leading-relaxed opacity-95">{body}</p>
          {alreadyCaptured ? (
            <p className="mt-1 text-[11px] opacity-90">
              This order had already been captured — the stored record was returned unchanged.
            </p>
          ) : null}
        </div>
      </div>

      <dl className="grid grid-cols-1 gap-y-3 px-5 py-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-[11px] uppercase tracking-[0.08em] text-faint">Amount</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-ink">
            {money(transaction.amount, transaction.currency)}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-[0.08em] text-faint">Status</dt>
          <dd className="mt-1">
            <StatusBadge status={transaction.status} />
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-[11px] uppercase tracking-[0.08em] text-faint">PayPal order</dt>
          <dd className="mt-0.5 break-all font-mono text-xs text-muted">
            {transaction.paypal_order_id}
          </dd>
        </div>
        {transaction.paypal_capture_id ? (
          <div className="sm:col-span-2">
            <dt className="text-[11px] uppercase tracking-[0.08em] text-faint">Capture id</dt>
            <dd className="mt-0.5 break-all font-mono text-xs text-muted">
              {transaction.paypal_capture_id}
            </dd>
          </div>
        ) : null}
        <div className="sm:col-span-2">
          <dt className="text-[11px] uppercase tracking-[0.08em] text-faint">Internal record</dt>
          <dd className="mt-0.5 break-all font-mono text-xs text-muted">{transaction.id}</dd>
        </div>
      </dl>

      <div className="flex flex-wrap gap-2 border-t border-white/8 px-5 py-4">
        <Link to={`/transactions/${transaction.id}`} className="btn btn-primary">
          View transaction
        </Link>
        <button type="button" className="btn btn-ghost" onClick={onReset}>
          Create another
        </button>
        <Link to="/" className="btn btn-ghost">
          Back to overview
        </Link>
      </div>
    </div>
  )
}
