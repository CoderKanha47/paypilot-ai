import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import {
  Activity,
  ArrowRight,
  CircleCheck,
  Clock3,
  CreditCard,
  PieChart as PieChartIcon,
  TrendingUp,
  Wallet,
  XCircle,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useApp } from '../context/AppContext'
import { useAsync } from '../hooks/useAsync'
import { api } from '../lib/api'
import { money, moneyShort } from '../lib/format'
import type { DashboardResponse } from '../lib/types'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { PageHeader } from '../components/PageHeader'
import { StatCard } from '../components/StatCard'
import { ChartSkeleton, StatCardSkeleton, TableSkeleton } from '../components/Skeleton'
import { TransactionTable } from '../components/TransactionTable'
import { ChartTooltip, AXIS_STYLE as AXIS } from '../components/chartParts'

const STATUS_COLORS: Record<string, string> = {
  completed: '#22c55e',
  pending: '#f59e0b',
  failed: '#ef4444',
  declined: '#f97316',
  cancelled: '#6b769a',
  expired: '#94a3b8',
  refunded: '#3b82f6',
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  return (
    <section className="card p-4 sm:p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-xs text-faint">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  )
}

export function Overview() {
  const { config } = useApp()
  const { data, loading, error, reload } = useAsync<DashboardResponse>(
    () => api.get<DashboardResponse>('/api/dashboard?months=6&recent=8'),
    [],
  )

  const currency = data?.metrics.primary_currency ?? config?.paypal.currency ?? 'USD'
  const metrics = data?.metrics

  return (
    <>
      <PageHeader
        title="Overview"
        description="Every figure below is calculated from the transactions stored in this application."
        actions={
          <>
            <span className="hidden items-center gap-1.5 rounded-lg border border-white/10 bg-navy-850 px-3 py-2 text-xs text-muted sm:flex">
              <Activity size={13} className="text-accent-soft" aria-hidden="true" />
              {data ? `Updated ${new Date().toLocaleTimeString()}` : 'Loading…'}
            </span>
            <button type="button" className="btn btn-ghost" onClick={reload}>
              Refresh
            </button>
          </>
        }
      />

      {error ? (
        <div className="mb-6">
          <ErrorBanner message={error} onRetry={reload} />
        </div>
      ) : null}

      {/* ---------------------------------------------------------- KPI row */}
      {loading || !metrics ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <StatCardSkeleton key={index} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Total captured"
            value={money(metrics.total_captured, metrics.primary_currency)}
            icon={Wallet}
            tone="success"
            hint={
              <span className="flex items-center gap-1.5">
                <TrendingUp size={12} aria-hidden="true" />
                {metrics.captured_count} completed payment
                {metrics.captured_count === 1 ? '' : 's'}
              </span>
            }
          />
          <StatCard
            label="Awaiting payment"
            value={money(metrics.total_pending, metrics.primary_currency)}
            icon={Clock3}
            tone="warning"
            hint={`${metrics.pending_count} open payment request${metrics.pending_count === 1 ? '' : 's'}`}
          />
          <StatCard
            label="Failed / declined"
            value={String(metrics.failed_count)}
            icon={XCircle}
            tone="danger"
            hint={
              metrics.failed_count > 0
                ? 'Needs a fresh order or a follow-up'
                : 'No failed payments recorded'
            }
          />
          <StatCard
            label="Success rate"
            value={`${metrics.success_rate.toFixed(1)}%`}
            icon={CircleCheck}
            tone="accent"
            hint={`${metrics.cancelled_count} cancelled or expired`}
          />
        </div>
      )}

      {metrics?.other_currencies.length ? (
        <div className="mt-4 rounded-lg border border-white/8 bg-white/[0.03] px-4 py-3 text-xs text-muted">
          Held in other currencies (never added to the {metrics.primary_currency} total):{' '}
          {metrics.other_currencies
            .map((entry) => `${money(entry.amount, entry.currency)} across ${entry.count}`)
            .join(' · ')}
        </div>
      ) : null}

      {metrics?.demo_data_included ? (
        <p className="mt-4 text-xs text-faint">
          <span className="tag border border-white/15 bg-white/6 text-[10px] text-muted">DEMO DATA</span>{' '}
          Part of this dashboard comes from clearly-labelled sample rows.
        </p>
      ) : null}

      {/* ----------------------------------------------------------- charts */}
      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          {loading || !data ? (
            <ChartSkeleton />
          ) : (
            <ChartCard
              title="Monthly collections"
              subtitle={`Completed payments only · ${currency}`}
            >
              <div className="h-[248px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.monthly} margin={{ top: 6, right: 8, bottom: 0, left: -12 }}>
                    <defs>
                      <linearGradient id="collectionFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#7c5cff" stopOpacity={0.55} />
                        <stop offset="100%" stopColor="#7c5cff" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} tick={AXIS} />
                    <YAxis
                      tickLine={false}
                      axisLine={false}
                      tick={AXIS}
                      width={58}
                      tickFormatter={(value: number | string) =>
                        moneyShort(String(value), currency).replace(` ${currency}`, '')
                      }
                    />
                    <Tooltip
                      content={<ChartTooltip />}
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      formatter={(value: any) => (value !== undefined ? money(String(value), currency) : "")}
                      labelFormatter={(_label, payload) => {
                        const point = payload?.[0]?.payload as { month?: string } | undefined
                        return point?.month ?? ""
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="amount"
                      name="Collected"
                      stroke="#7c5cff"
                      strokeWidth={2.4}
                      fill="url(#collectionFill)"
                      dot={{ r: 3, fill: '#7c5cff', strokeWidth: 0 }}
                      activeDot={{ r: 5, fill: '#a68dff' }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          )}
        </div>

        {loading || !data ? (
          <ChartSkeleton />
        ) : (
          <ChartCard title="Status distribution" subtitle="All recorded payments">
            {metrics && metrics.total_transactions === 0 ? (
              <div className="grid h-[248px] place-items-center text-center text-xs text-faint">
                No payments recorded yet.
              </div>
            ) : (
              <div className="flex h-[248px] flex-col">
                <div className="min-h-0 flex-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={data.status_distribution.filter((entry) => entry.count > 0)}
                        dataKey="count"
                        nameKey="status"
                        innerRadius="58%"
                        outerRadius="86%"
                        paddingAngle={3}
                        stroke="none"
                      >
                        {data.status_distribution
                          .filter((entry) => entry.count > 0)
                          .map((entry) => (
                            <Cell
                              key={entry.status}
                              fill={STATUS_COLORS[entry.status] ?? '#7c5cff'}
                            />
                          ))}
                      </Pie>
                      <Tooltip content={<ChartTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <ul className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px]">
                  {data.status_distribution
                    .filter((entry) => entry.count > 0)
                    .map((entry) => (
                      <li key={entry.status} className="flex items-center gap-1.5 text-muted">
                        <span
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{ backgroundColor: STATUS_COLORS[entry.status] ?? '#7c5cff' }}
                          aria-hidden="true"
                        />
                        <span className="capitalize">{entry.status}</span>
                        <span className="ml-auto tabular-nums text-faint">{entry.count}</span>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </ChartCard>
        )}
      </div>

      {/* --------------------------------------------------- recent activity */}
      <section className="card mt-6 overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-white/8 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">Recent transactions</h2>
            <p className="mt-0.5 text-xs text-faint">Newest first, straight from SQLite</p>
          </div>
          <Link
            to="/transactions"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-accent-soft hover:text-accent"
          >
            View all <ArrowRight size={13} aria-hidden="true" />
          </Link>
        </div>
        {loading ? (
          <div className="p-5">
            <TableSkeleton rows={5} />
          </div>
        ) : data && data.recent.length === 0 ? (
          <div className="px-5 py-8">
            <EmptyState
              icon={CreditCard}
              title="No payments yet"
              description="Create your first payment request and approve it through PayPal Sandbox — it will show up here instantly."
              action={
                <Link to="/new-payment" className="btn btn-primary">
                  Create a payment request
                </Link>
              }
            />
          </div>
        ) : data ? (
          <TransactionTable rows={data.recent} compact />
        ) : null}
      </section>

      {!loading && !data && !error ? (
        <div className="mt-6">
          <EmptyState
            icon={PieChartIcon}
            title="Nothing to show"
            description="There are no transactions in this database yet."
          />
        </div>
      ) : null}
    </>
  )
}
