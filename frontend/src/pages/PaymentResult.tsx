import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, XOctagon, ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../lib/api";
import { money } from "../lib/format";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";

type ResultPhase = "capturing" | "success" | "failed" | "cancelled" | "error";

export function PaymentResult() {
  const [searchParams] = useSearchParams();

  const token = searchParams.get("token");
  const cancelled = searchParams.get("cancelled") === "true";

  const [phase, setPhase] = useState<ResultPhase>(cancelled ? "cancelled" : "capturing");
  const [transaction, setTransaction] = useState<{ id: string; amount: string; currency: string; status: string; paypal_order_id: string; paypal_capture_id: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cancelled) {
      setPhase("cancelled");
      return;
    }

    if (!token) {
      setError("Missing PayPal order token. Return to the dashboard and try again.");
      setPhase("error");
      return;
    }

    const capture = async () => {
      try {
        const res = await api.post<{ transaction: typeof transaction }>("/api/payments/capture-order", {
          order_id: token,
        });
        if (res.transaction) {
          setTransaction(res.transaction);
          setPhase(res.transaction.status === "completed" ? "success" : "failed");
        }
      } catch (err) {
        setError(errorMessage(err));
        setPhase("error");
      }
    };

    capture();
  }, [token, cancelled]);

  if (phase === "capturing") {
    return (
      <div className="mx-auto max-w-md text-center py-12">
        <Loader2 size={48} className="mx-auto animate-spin text-violet-500" aria-hidden="true" />
        <h1 className="mt-4 text-lg font-semibold">Capturing payment…</h1>
        <p className="mt-1 text-sm text-slate-500">Verifying with PayPal and recording the transaction.</p>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="mx-auto max-w-md text-center py-12">
        <XOctagon size={48} className="mx-auto text-rose-500" aria-hidden="true" />
        <h1 className="mt-4 text-lg font-semibold">Capture failed</h1>
        <p className="mt-1 text-sm text-slate-500">{error}</p>
        <Link to="/" className="btn btn-primary mt-5 inline-block">
          <ArrowLeft size={15} className="mr-1" /> Back to dashboard
        </Link>
      </div>
    );
  }

  if (phase === "cancelled") {
    return (
      <div className="mx-auto max-w-md text-center py-12">
        <ArrowLeft size={48} className="mx-auto text-slate-400" aria-hidden="true" />
        <h1 className="mt-4 text-lg font-semibold">Payment cancelled</h1>
        <p className="mt-1 text-sm text-slate-500">You cancelled the payment in PayPal. Nothing was charged.</p>
        <Link to="/" className="btn btn-primary mt-5 inline-block">
          <ArrowLeft size={15} className="mr-1" /> Back to dashboard
        </Link>
      </div>
    );
  }

  const isSuccess = phase === "success";

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader
        title={isSuccess ? "Payment captured" : "Payment not completed"}
        description={isSuccess ? "The payment was captured and recorded." : "PayPal did not complete this payment."}
      />

      <div className="card p-6">
        <div className={`flex items-start gap-3 ${isSuccess ? "border-b border-success/30" : "border-b border-rose-500/30"}`}>
          <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg ${isSuccess ? "bg-success/12 text-success" : "bg-rose-500/12 text-rose-500"}`}>
            {isSuccess ? <CheckCircle2 size={20} /> : <XOctagon size={20} />}
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold">{isSuccess ? "Payment captured" : "Payment not completed"}</h2>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              {isSuccess
                ? `${money(transaction?.amount ?? "", transaction?.currency ?? "USD")} was captured and recorded.`
                : "PayPal returned a non-completed status. No money was collected."}
            </p>
          </div>
          <StatusBadge status={transaction?.status ?? "pending"} />
        </div>

        {transaction && (
          <dl className="mt-4 grid grid-cols-1 gap-y-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[11px] uppercase tracking-[0.08em] text-slate-500">Amount</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-slate-900">{money(transaction.amount, transaction.currency)}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-[0.08em] text-slate-500">Status</dt>
              <dd className="mt-1"><StatusBadge status={transaction.status} /></dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-[11px] uppercase tracking-[0.08em] text-slate-500">PayPal order</dt>
              <dd className="mt-0.5 break-all font-mono text-xs text-slate-500">{transaction.paypal_order_id}</dd>
            </div>
            {transaction.paypal_capture_id ? (
              <div className="sm:col-span-2">
                <dt className="text-[11px] uppercase tracking-[0.08em] text-slate-500">Capture id</dt>
                <dd className="mt-0.5 break-all font-mono text-xs text-slate-500">{transaction.paypal_capture_id}</dd>
              </div>
            ) : null}
            <div className="sm:col-span-2">
              <dt className="text-[11px] uppercase tracking-[0.08em] text-slate-500">Internal record</dt>
              <dd className="mt-0.5 break-all font-mono text-xs text-slate-500">{transaction.id}</dd>
            </div>
          </dl>
        )}

        <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-200 pt-4">
          {transaction ? (
            <Link to={`/transactions/${transaction.id}`} className="btn btn-primary">
              View transaction
            </Link>
          ) : null}
          <Link to="/" className="btn btn-ghost">
            <ArrowLeft size={15} className="mr-1" /> Back to overview
          </Link>
        </div>
      </div>
    </div>
  );
}