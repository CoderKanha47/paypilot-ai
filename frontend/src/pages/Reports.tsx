import { FileJson, FileSpreadsheet, Printer, Sparkles } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { formatDateTime, money } from "../lib/format";
import { StatusBadge } from "../components/StatusBadge";
import { TableSkeleton } from "../components/Skeleton";
import { ErrorBanner } from "../components/ErrorBanner";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import type { ReportSummaryResponse, StatusCount } from "../lib/types";

export function Reports() {
  const summary = useAsync(() => api.get<ReportSummaryResponse>("/api/reports/summary"), []);
  const data = summary.data;

  if (summary.loading) return <TableSkeleton rows={8} />;
  if (summary.error || !data) {
    return <ErrorBanner title="Could not build the report" message={summary.error ?? "Unknown error"} onRetry={summary.reload} />;
  }

  const maxStatus = Math.max(1, ...data.status_breakdown.map((s: StatusCount) => s.count));

  return (
    <div className="space-y-6 print:bg-white">
      <PageHeader
        title="Reports"
        description="Period summary plus downloadable CSV / JSON exports."
        actions={
          <>
            <a className="btn btn-ghost inline-flex items-center gap-2" href="/api/reports/transactions.csv" target="_blank" rel="noreferrer">
              <FileSpreadsheet size={15} /> CSV
            </a>
            <a className="btn btn-ghost inline-flex items-center gap-2" href="/api/reports/transactions.json" target="_blank" rel="noreferrer">
              <FileJson size={15} /> JSON
            </a>
            <button className="btn btn-ghost hidden print:hidden sm:inline-flex" onClick={() => window.print()}>
              <Printer size={15} className="mr-1" /> Print
            </button>
          </>
        }
      />

      <div className="card p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold">PayPilot AI — Operations report</h2>
            <p className="text-sm text-muted">
              Period: {formatDateTime(data.monthly[0]?.month ?? data.generated_at)} → {formatDateTime(data.generated_at)}
            </p>
          </div>
          <p className="text-xs text-faint">
            Generated {formatDateTime(data.generated_at)} · currency: {data.currency}
          </p>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-navy-700/15 pt-5 sm:grid-cols-4">
          {[
            ["Transactions", String(data.transaction_count)],
            ["Captured volume", money(data.total_captured, data.currency)],
            ["Pending", money(data.total_pending, data.currency)],
            ["Status types", String(data.status_breakdown.length)],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-faint">{label}</dt>
              <dd className="mt-1 text-lg font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card p-6">
          <h3 className="text-sm font-semibold">By status</h3>
          <ul className="mt-4 space-y-3">
            {data.status_breakdown.map((entry: StatusCount) => (
              <li key={entry.status}>
                <div className="flex items-center justify-between text-sm">
                  <StatusBadge status={entry.status} />
                  <span className="text-muted">
                    {entry.count} · {money(entry.amount, entry.currency)}
                  </span>
                </div>
                <div className="mt-1.5 h-2 rounded-full bg-navy-700/15">
                  <div className="h-2 rounded-full bg-accent" style={{ width: `${(entry.count / maxStatus) * 100}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="card p-6">
          <h3 className="text-sm font-semibold">By currency</h3>
          <table className="mt-4 w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-faint">
              <tr>
                <th className="pb-2">Currency</th>
                <th className="pb-2 text-right">Count</th>
                <th className="pb-2 text-right">Captured</th>
                <th className="pb-2 text-right">Pending</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-700/15">
              {Object.entries(
                data.status_breakdown.reduce(
                  (acc: Record<string, { count: number; captured: number; pending: number }>, s: StatusCount) => {
                    acc[s.currency] = acc[s.currency] ?? { count: 0, captured: 0, pending: 0 };
                    acc[s.currency].count += s.count;
                    return acc;
                  },
                  {}
                )
              ).map(([currency, row]) => (
                <tr key={currency}>
                  <td className="py-2 font-medium">{currency}</td>
                  <td className="py-2 text-right">{row.count}</td>
                  <td className="py-2 text-right">{money(data.total_captured, currency)}</td>
                  <td className="py-2 text-right">{money(data.total_pending, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="text-sm font-semibold">Executive summary</h3>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-muted">
          {data.notes.length === 0 && <EmptyState icon={Sparkles} title="No narrative" description="No activity in this period." />}
          {data.notes.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}