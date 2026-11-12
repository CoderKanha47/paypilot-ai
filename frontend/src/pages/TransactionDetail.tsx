import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Copy, ExternalLink, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { formatDateTime, money } from "../lib/format";
import { useAsync } from "../hooks/useAsync";
import { useApp } from "../context/AppContext";
import { StatusBadge } from "../components/StatusBadge";
import { TableSkeleton } from "../components/Skeleton";
import { ErrorBanner } from "../components/ErrorBanner";
import type { Transaction, TransactionDetail } from "../lib/types";

export function TransactionDetail() {
  const { id } = useParams();
  const { config } = useApp();
  const detail = useAsync(() => api.get<TransactionDetail>(`/api/transactions/${id!}`), [id]);
  const [syncing, setSyncing] = useState(false);

  const tx = detail.data;

  const sync = useCallback(async () => {
    if (!tx || tx.mode !== "sandbox" || !tx.paypal_order_id) return;
    setSyncing(true);
    try {
      await api.get<{ transaction: Transaction }>(`/api/payments/order/${tx.paypal_order_id}`);
      await detail.reload();
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setSyncing(false);
    }
  }, [detail, tx]);

  useEffect(() => {
    if (tx && tx.mode === "sandbox" && tx.status === "pending" && tx.paypal_order_id) {
      void sync();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tx?.id]);

  if (detail.loading) return <TableSkeleton rows={8} />;
  if (detail.error || !tx) {
    return (
      <ErrorBanner
        title="Transaction not found"
        message={detail.error ?? "No transaction with that id."}
        onRetry={detail.reload}
      />
    );
  }

  const rows: Array<[string, string]> = [
    ["Internal id", tx.id],
    ["PayPal order", tx.paypal_order_id ?? "—"],
    ["PayPal capture", tx.paypal_capture_id ?? "—"],
    ["Description", tx.description],
    ["Created", formatDateTime(tx.created_at)],
    ["Updated", formatDateTime(tx.updated_at)],
    ["Mode", tx.mode === "sandbox" ? "PayPal Sandbox" : "Demo simulation"],
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <Link to="/transactions" className="link inline-flex items-center gap-1 text-sm">
        <ArrowLeft size={14} /> Back to transactions
      </Link>

      <div className="card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="mt-1 text-3xl font-semibold tracking-tight">{money(tx.amount, tx.currency)}</p>
            <p className="mt-1 text-sm text-muted">{tx.description}</p>
          </div>
          <StatusBadge status={tx.status} size="md" />
        </div>

        <dl className="mt-6 grid gap-x-8 gap-y-3 border-t border-navy-700/15 pt-5 text-sm sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-3 sm:justify-start">
              <dt className="text-muted">{label}</dt>
              <dd className="flex items-center gap-2 font-medium">
                <span className="max-w-[22ch] truncate sm:max-w-[32ch]" title={value}>{value}</span>
                <button
                  className="text-faint hover:text-ink"
                  title={`Copy ${label}`}
                  onClick={() => {
                    void navigator.clipboard?.writeText(value);
                  }}
                >
                  <Copy size={13} />
                </button>
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-navy-700/15 pt-5">
          {config?.paypal.configured && tx.mode === "sandbox" && tx.paypal_order_id && (
            <a
              className="btn btn-ghost inline-flex items-center gap-2"
              href={`https://www.sandbox.paypal.com/checkoutnow?token=${tx.paypal_order_id}`}
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink size={15} /> Open in PayPal Sandbox
            </a>
          )}
          {tx.mode === "sandbox" && tx.paypal_order_id && (
            <button className="btn btn-ghost inline-flex items-center gap-2" onClick={() => void sync()} disabled={syncing}>
              <RefreshCw size={15} className={syncing ? "animate-spin" : ""} /> Re-sync order
            </button>
          )}
          {tx.mode === "demo" && (
            <p className="text-xs text-faint">
              This record was produced by the labelled demo simulator — no money moved.
            </p>
          )}
        </div>
      </div>

      <div className="card p-6">
        <h3 className="text-sm font-semibold">Status history</h3>
        <ol className="mt-4 space-y-4 border-l border-navy-700/15 pl-5">
          {tx.events?.map((event) => (
            <li key={event.id} className="relative">
              <span className="absolute -left-[27px] top-1.5 h-3 w-3 rounded-full border-2 border-white bg-accent" />
              <div className="flex items-center gap-3">
                <StatusBadge status={event.status} size="sm" />
                <span className="text-xs text-faint">{formatDateTime(event.created_at)}</span>
              </div>
              <p className="mt-1 text-sm text-muted">
                {event.event_type === "sync" ? "Reconciled from PayPal" : `Recorded by ${event.event_type}`}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}