import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { TableSkeleton } from "../components/Skeleton";
import { PageHeader } from "../components/PageHeader";
import type { AppConfig, HealthResponse } from "../lib/types";

function Dot({ ok }: { ok: boolean }) {
  return ok ? <CheckCircle2 size={16} className="text-success" /> : <XCircle size={16} className="text-danger" />;
}

export function Settings() {
  const cfg = useAsync(() => api.get<AppConfig>("/api/config"), []);
  const health = useAsync(() => api.get<HealthResponse>("/api/health"), []);
  const config = cfg.data;

  if (cfg.loading || health.loading) return <TableSkeleton rows={6} />;

  const checks = [
    {
      ok: Boolean(config?.paypal.configured),
      title: "PayPal sandbox credentials",
      detail: config?.paypal.configured
        ? `Configured for ${config.paypal.mode === "sandbox" ? "Sandbox" : config.paypal.mode === "live" ? "LIVE" : "demo"} as ${config.paypal.client_id.slice(0, 8)}…`
        : "Not configured — the app is running the labelled demo checkout simulator.",
    },
    {
      ok: config?.ai.provider !== "demo",
      title: "AI provider",
      detail:
        config?.ai.provider === "demo"
          ? "Demo AI mode — deterministic, database-grounded answers. Add OPENAI_API_KEY or ANTHROPIC_API_KEY."
          : `Provider: ${config?.ai.provider} (${config?.ai.model})`,
    },
    {
      ok: Boolean(config?.demo_data_seeded),
      title: "Demo dataset",
      detail: config?.demo_data_seeded
        ? "Sample transactions are present and clearly marked as demo records."
        : "No demo data seeded — your tables are clean.",
    },
    {
      ok: health.data?.status === "ok",
      title: "Backend health",
      detail: `HTTP ${health.data?.status ?? "?"} · DB: ${health.data?.database ?? "?"}`,
    },
  ];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Settings & setup" description="Runtime configuration read from the server environment." />

      <div className="card p-6">
        <h3 className="text-sm font-semibold">Readiness checks</h3>
        <ul className="mt-4 divide-y divide-navy-700/15">
          {checks.map((c) => (
            <li key={c.title} className="flex items-start gap-3 py-3">
              <span className="mt-0.5"><Dot ok={c.ok} /></span>
              <div>
                <p className="text-sm font-medium">{c.title}</p>
                <p className="text-sm text-muted">{c.detail}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="card p-6">
        <h3 className="text-sm font-semibold">Environment variables</h3>
        <p className="mt-1 text-sm text-muted">
          Copy <code className="rounded bg-navy-700/15 px-1">.env.example</code> to <code className="rounded bg-navy-700/15 px-1">.env</code> and fill in
          the values. Keys never travel to the browser — the server reads them at startup.
        </p>
        <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          {[
            ["PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET", "Sandbox REST app credentials"],
            ["PAYPAL_ENV", "sandbox (only sandbox is supported)"],
            ["PAYPAL_MODE", "live to use real Orders v2 API"],
            ["AI_PROVIDER", "demo | openai | anthropic | openai_compatible"],
            ["OPENAI_API_KEY / ANTHROPIC_API_KEY", "Server-side only, never exposed"],
            ["SEED_DEMO_DATA", "true to load the labelled sample dataset"],
          ].map(([key, desc]) => (
            <div key={key} className="rounded-xl border border-navy-700/15 p-3">
              <p className="font-mono text-xs text-accent-soft">{key}</p>
              <p className="mt-1 text-xs text-faint">{desc}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-start gap-2 rounded-xl bg-warning/10 p-3 text-sm text-warning">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <p>
            PayPal <strong>sandbox only</strong>. Never paste production credentials or real card numbers — the app
            refuses non-sandbox environments by design.
          </p>
        </div>
      </div>
    </div>
  );
}