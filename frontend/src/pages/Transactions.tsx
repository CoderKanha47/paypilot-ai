import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Download, Inbox, PlusCircle, ReceiptText, Search, X } from 'lucide-react'
import { useAsync } from '../hooks/useAsync'
import { api } from '../lib/api'
import type { TransactionListResponse } from '../lib/types'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { TableSkeleton } from '../components/Skeleton'
import { TransactionTable } from '../components/TransactionTable'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'completed', label: 'Completed' },
  { value: 'pending', label: 'Pending' },
  { value: 'failed', label: 'Failed' },
  { value: 'declined', label: 'Declined' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'expired', label: 'Expired' },
  { value: 'refunded', label: 'Refunded' },
  { value: 'failed_or_cancelled', label: 'Failed or cancelled' },
]

const PAGE_SIZE = 25

export function Transactions() {
  const [params, setParams] = useSearchParams()

  const search = params.get('search') ?? ''
  const status = params.get('status') ?? ''
  const dateFrom = params.get('date_from') ?? ''
  const dateTo = params.get('date_to') ?? ''
  const offset = Number(params.get('offset') ?? '0') || 0

  const query = useMemo(() => {
    const searchParams = new URLSearchParams()
    searchParams.set('limit', String(PAGE_SIZE))
    searchParams.set('offset', String(offset))
    if (search) searchParams.set('search', search)
    if (status) searchParams.set('status', status)
    if (dateFrom) searchParams.set('date_from', dateFrom)
    if (dateTo) searchParams.set('date_to', dateTo)
    return searchParams.toString()
  }, [search, status, dateFrom, dateTo, offset])

  const { data, loading, error, reload } = useAsync<TransactionListResponse>(
    () => api.get<TransactionListResponse>(`/api/transactions?${query}`),
    [query],
  )

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    Object.entries(patch).forEach(([key, value]) => {
      if (value === null || value === '') next.delete(key)
      else next.set(key, value)
    })
    // Any filter change returns to the first page.
    if (!('offset' in patch)) next.delete('offset')
    setParams(next, { replace: true })
  }

  const hasFilters = Boolean(search || status || dateFrom || dateTo)
  const total = data?.total ?? 0
  const items = data?.items ?? []

  return (
    <>
      <PageHeader
        title="Transactions"
        description="Search, filter and inspect every payment record, including PayPal order and capture references."
        actions={
          <a href="/api/reports/transactions.csv" className="btn btn-ghost" download>
            <Download size={15} aria-hidden="true" /> Export CSV
          </a>
        }
      />

      {/* ------------------------------------------------------------ filters */}
      <div className="card mb-5 p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="relative xl:col-span-1">
            <Search
              size={15}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint"
              aria-hidden="true"
            />
            <label htmlFor="txn-search" className="sr-only">
              Search transactions
            </label>
            <input
              id="txn-search"
              className="input pl-9"
              placeholder="Search description, reference, order id…"
              value={search}
              onChange={(event) => update({ search: event.target.value })}
            />
          </div>

          <div>
            <label htmlFor="txn-status" className="sr-only">
              Status
            </label>
            <select
              id="txn-status"
              className="input"
              value={status}
              onChange={(event) => update({ status: event.target.value })}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="txn-from" className="sr-only">
              From date
            </label>
            <input
              id="txn-from"
              type="date"
              className="input"
              value={dateFrom}
              onChange={(event) => update({ date_from: event.target.value })}
            />
          </div>

          <div>
            <label htmlFor="txn-to" className="sr-only">
              To date
            </label>
            <input
              id="txn-to"
              type="date"
              className="input"
              value={dateTo}
              onChange={(event) => update({ date_to: event.target.value })}
            />
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-faint">
            {loading ? 'Loading…' : `${total} record${total === 1 ? '' : 's'} matched`}
          </p>
          {hasFilters ? (
            <button
              type="button"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-muted hover:text-ink"
              onClick={() => setParams(new URLSearchParams(), { replace: true })}
            >
              <X size={13} aria-hidden="true" /> Clear filters
            </button>
          ) : null}
        </div>
      </div>

      {error ? <div className="mb-5"><ErrorBanner message={error} onRetry={reload} /></div> : null}

      {/* -------------------------------------------------------------- table */}
      {loading ? (
        <TableSkeleton rows={8} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={hasFilters ? Inbox : ReceiptText}
          title={hasFilters ? 'No transactions match' : 'No transactions yet'}
          description={
            hasFilters
              ? 'Try widening the date range or clearing the status filter.'
              : 'Payment requests you create will be stored here with their PayPal order and capture references.'
          }
          action={
            hasFilters ? (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setParams(new URLSearchParams(), { replace: true })}
              >
                Clear filters
              </button>
            ) : (
              <Link to="/new-payment" className="btn btn-primary">
                <PlusCircle size={15} aria-hidden="true" /> Create a payment
              </Link>
            )
          }
        />
      ) : (
        <div className="card overflow-hidden">
          <TransactionTable rows={items} />
          <div className="flex flex-col gap-3 border-t border-white/8 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-faint">
              Showing <span className="tabular-nums text-muted">{offset + 1}</span>–
              <span className="tabular-nums text-muted">{Math.min(offset + PAGE_SIZE, total)}</span> of{' '}
              <span className="tabular-nums text-muted">{total}</span>
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn btn-ghost !py-1.5 text-xs"
                disabled={offset === 0}
                onClick={() => update({ offset: String(Math.max(0, offset - PAGE_SIZE)) })}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn btn-ghost !py-1.5 text-xs"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => update({ offset: String(offset + PAGE_SIZE) })}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
