import { ArrowUpRight, FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { formatDateTime, money, relativeTime, truncate } from '../lib/format'
import type { Transaction } from '../lib/types'
import { StatusBadge } from './StatusBadge'

interface TransactionTableProps {
  rows: Transaction[]
  compact?: boolean
  emptyMessage?: string
}

export function TransactionTable({ rows, compact = false, emptyMessage }: TransactionTableProps) {
  if (rows.length === 0) {
    return (
      <div className="px-5 py-10 text-center text-sm text-muted">
        {emptyMessage ?? 'No transactions match the current filters.'}
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="border-b border-navy-700/15 text-[11px] uppercase tracking-[0.08em] text-faint">
            <th scope="col" className="px-5 py-3 font-semibold">Description</th>
            <th scope="col" className="px-3 py-3 font-semibold">Status</th>
            {!compact ? (
              <th scope="col" className="px-3 py-3 font-semibold">Reference</th>
            ) : null}
            <th scope="col" className="px-3 py-3 font-semibold">Created</th>
            <th scope="col" className="px-3 py-3 text-right font-semibold">Amount</th>
            <th scope="col" className="px-5 py-3" aria-label="Open" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className="border-b border-navy-700/15 transition last:border-0 hover:bg-navy-800/10"
            >
              <td className="px-5 py-3.5">
                <Link
                  to={`/transactions/${row.id}`}
                  className="group flex items-center gap-2 font-medium text-ink hover:text-accent-soft"
                >
                  <FileText size={14} className="shrink-0 text-faint group-hover:text-accent-soft" aria-hidden="true" />
                  <span className="truncate">{truncate(row.description, 44)}</span>
                </Link>
                <div className="mt-1 flex flex-wrap items-center gap-2 pl-6 text-[11px] text-faint">
                  <span className="font-mono">{row.paypal_order_id}</span>
                  {row.is_demo_record ? (
                    <span className="tag border border-navy-700/20 bg-navy-800/10 text-[9px] text-muted">
                      DEMO RECORD
                    </span>
                  ) : null}
                  {row.mode === 'sandbox' ? (
                    <span className="tag border border-success/25 bg-success/10 text-[9px] text-success">
                      SANDBOX
                    </span>
                  ) : null}
                </div>
              </td>
              <td className="px-3 py-3.5">
                <StatusBadge status={row.status} />
              </td>
              {!compact ? (
                <td className="px-3 py-3.5 font-mono text-xs text-muted">
                  {row.customer_reference || '—'}
                </td>
              ) : null}
              <td className="px-3 py-3.5">
                <div className="text-xs text-muted">{formatDateTime(row.created_at)}</div>
                <div className="text-[11px] text-faint">{relativeTime(row.created_at)}</div>
              </td>
              <td className="px-3 py-3.5 text-right font-medium tabular-nums text-ink">
                {money(row.amount, row.currency)}
              </td>
              <td className="px-5 py-3.5 text-right">
                <Link
                  to={`/transactions/${row.id}`}
                  className="inline-flex rounded-md p-1.5 text-faint transition hover:bg-navy-800/10 hover:text-ink"
                  aria-label={`Open ${row.description}`}
                >
                  <ArrowUpRight size={15} aria-hidden="true" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
