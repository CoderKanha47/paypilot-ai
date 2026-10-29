# PayPilot AI — Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PAYPILOT AI SYSTEM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐        │
│  │   BROWSER    │◄───────►│   BACKEND    │◄───────►│   PAYPAL     │        │
│  │  (React/TS)  │  HTTPS  │  (FastAPI)   │  HTTPS  │  SANDBOX API │        │
│  └──────────────┘         └──────────────┘         └──────────────┘        │
│        │                         │                        │                │
│        │                         ▼                        │                │
│        │                  ┌──────────────┐               │                │
│        │                  │   AI PROVIDER│               │                │
│        │                  │ (OpenAI/etc) │               │                │
│        │                  └──────────────┘               │                │
│        │                         │                        │                │
│        │                         ▼                        │                │
│        │                  ┌──────────────┐               │                │
│        └─────────────────►│   SQLITE DB  │               │                │
│                           └──────────────┘               │                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Diagram

### Frontend (React + TypeScript + Vite)

```
src/
├── components/          # Reusable UI components
│   ├── Layout.tsx       # App shell with navigation
│   ├── PayPalCheckout.tsx  # Official PayPal JS SDK integration
│   ├── TransactionTable.tsx
│   ├── StatCard.tsx
│   ├── Chart components (Recharts)
│   └── ... (skeletons, badges, etc.)
├── pages/               # Route-level components
│   ├── Overview.tsx     # Dashboard with metrics & charts
│   ├── Transactions.tsx # Searchable/filterable history
│   ├── TransactionDetail.tsx
│   ├── NewPayment.tsx   # Payment creation + approval flow
│   ├── Assistant.tsx    # Chat-style AI interface
│   ├── Reports.tsx      # Exports + printable summary
│   └── Settings.tsx     # Readiness checks + env docs
├── context/
│   └── AppContext.tsx   # Global config/health state
├── hooks/
│   └── useAsync.ts      # Async data fetching hook
├── lib/
│   ├── api.ts           # Typed fetch client + error handling
│   ├── format.ts        # Money/date formatting
│   └── types.ts         # Shared API response types
└── main.tsx             # Entry point
```

### Backend (FastAPI + Python 3.12)

```
app/
├── main.py              # FastAPI factory, lifespan, middleware, SPA serving
├── config.py            # Pydantic Settings (env-driven, validated)
├── database.py          # SQLAlchemy engine/session (SQLite, WAL mode)
├── models.py            # ORM models (Transaction, AppMeta)
├── schemas.py           # Pydantic request/response models
├── deps.py              # FastAPI dependencies (checkout, AI provider, DB)
├── errors.py            # Domain/PayPal/AI error types + HTTP helpers
├── money.py             # Integer minor-unit arithmetic (Decimal at edges)
├── rate_limit.py        # In-process sliding-window limiter
├── logging_config.py    # Structured JSON/text logging, secret redaction
├── seed.py              # Clearly-labelled demo data (is_demo_record=True)
├── routers/             # API route modules
│   ├── health.py        # /health, /config, /health/db
│   ├── dashboard.py     # /dashboard (analytics)
│   ├── transactions.py  # /transactions (list, detail)
│   ├── payments.py      # /payments (create, capture, cancel, sync)
│   ├── assistant.py     # /assistant (chat, suggestions)
│   └── reports.py       # /reports (csv, json, summary)
└── services/            # Business logic
    ├── paypal.py        # Official PayPal REST client (OAuth, Orders v2)
    ├── payments.py      # Payment orchestration (ownership, validation)
    ├── demo_checkout.py # Local simulator when PayPal creds absent
    ├── ai.py            # Provider abstraction (OpenAI, Anthropic, demo)
    ├── assistant.py     # Grounded assistant pipeline (context→compute→prompt)
    ├── analytics.py     # Dashboard metrics (exact integer math)
    ├── repository.py    # Transaction query helpers
    └── serializers.py   # ORM → API serialization
```

## Data Flow: Payment Creation → Approval → Capture

```
1. USER SUBMITS FORM
   └─► POST /api/payments/create-order {amount, currency, description, reference}

2. BACKEND VALIDATES & CREATES ORDER
   ├─► Validate amount/currency (integer minor units)
   ├─► PayPalService.create_order() → POST /v2/checkout/orders (OAuth token)
   ├─► Persist Transaction row (status=pending, mode=sandbox|demo)
   └─► Return {transaction_id, order_id, approval_url, mode, notice}

3. FRONTEND RENDERS PAYPAL CHECKOUT
   ├─► Load PayPal JS SDK (client-id from response)
   ├─► PayPalCheckout component renders buttons with createOrder=()=>orderId
   └─► Payer approves in PayPal Sandbox hosted experience

4. PAYPAL CALLBACK → FRONTEND onApprove(data.orderID)
   └─► POST /api/payments/capture-order {order_id, transaction_id}

5. BACKEND CAPTURES & VERIFIES
   ├─► Find local Transaction by order_id (ownership check)
   ├─► PayPalService.capture_order() → POST /v2/checkout/orders/{id}/capture
   ├─► Validate returned amount/currency match local record
   ├─► Update Transaction (status, capture_id, captured_minor, completed_at)
   └─► Return {transaction, already_captured, mode, notice}

6. FRONTEND SHOWS RESULT
   └─► Success/Declined/Failed/Pending panel with transaction details
```

## Data Flow: AI Assistant Query

```
1. USER ASKS QUESTION
   └─► POST /api/assistant/chat {message, history}

2. BACKEND BUILDS CONTEXT (async thread)
   ├─► Fetch all transactions from SQLite
   ├─► Compute ALL totals in Python (integer minor units):
   │   ├─► All-time captured, this week, this month
   │   ├─► Pending amount/count
   │   ├─► Failed/declined/expired counts
   │   ├─► Monthly trends (last 6 months)
   │   └─► Records needing attention (failed + stale pending)
   ├─► Classify intent (weekly_total, pending, summary, etc.)
   ├─► Minimize & PII-scrub transaction refs for context
   └─► Build JSON context block + system prompt

3. AI PROVIDER CALL
   ├─► DemoAIProvider (deterministic, rule-based) OR
   ├─► OpenAIProvider (Chat Completions, JSON mode) OR
   ├─► AnthropicProvider (Messages API) OR
   └─► OpenAICompatibleProvider (Ollama, LM Studio, Groq...)

4. RESPONSE VALIDATION
   ├─► Extract JSON from model output
   ├─► Verify required fields (answer, facts, recommendations, references, confidence)
   ├─► Filter references to only known transaction IDs
   ├─► Scan for leaked secrets (PayPal secret, AI keys)
   └─► On failure: one corrective retry with stricter prompt

5. RETURN STRUCTURED RESPONSE
   └─► {answer, facts[], recommendations[], references[], confidence, provider, mode, latency_ms, disclaimer, notice, suggestions[]}
```

## Database Schema

```sql
-- Transactions (payment requests & captured payments)
CREATE TABLE transactions (
    id              TEXT PRIMARY KEY,           -- txn_<uuid24>
    paypal_order_id TEXT UNIQUE NOT NULL,       -- PayPal order ID
    paypal_capture_id TEXT,                     -- PayPal capture ID
    paypal_intent   TEXT DEFAULT 'CAPTURE',
    status          TEXT DEFAULT 'pending',     -- app status
    paypal_status   TEXT,                       -- raw PayPal status
    amount_minor    INTEGER NOT NULL,           -- integer minor units
    currency        TEXT(3) NOT NULL,           -- ISO-4217
    description     TEXT NOT NULL DEFAULT '',
    customer_reference TEXT,
    customer_note   TEXT,
    approval_url    TEXT,
    failure_reason  TEXT,
    mode            TEXT DEFAULT 'sandbox',     -- 'sandbox' | 'demo'
    is_demo_record  BOOLEAN DEFAULT FALSE,
    amount_captured_minor INTEGER,
    fee_minor       INTEGER,
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL,
    completed_at    DATETIME
);

-- Indexes
CREATE INDEX ix_transactions_status_created ON transactions(status, created_at);
CREATE INDEX ix_transactions_created_at ON transactions(created_at);
CREATE INDEX ix_transactions_capture_id ON transactions(paypal_capture_id);

-- App metadata (demo seed marker, etc.)
CREATE TABLE app_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  DATETIME NOT NULL
);
```

## Money Handling

- **Storage**: `amount_minor` (INTEGER) + `currency` (TEXT) — exact, no floats
- **Arithmetic**: All sums/comparisons in Python using `int` minor units
- **Display**: `decimal.Decimal` only at serialization edge (`format_amount()`)
- **Validation**: `parse_amount_to_minor()` rejects non-numeric, negative, zero, oversized
- **Currencies**: Supports 2-decimal (USD, EUR...) and 0-decimal (JPY, KRW...) via `minor_exponent()`

## Security Boundaries

| Boundary | Protection |
|----------|------------|
| Browser ↔ Backend | CORS restricted to configured origins; no credentials |
| Backend ↔ PayPal | OAuth 2.0 client credentials; token cached with refresh margin; 401 retry |
| Backend ↔ AI | API keys never leave server; context minimized; response validated |
| Database | SQLite file permissions; no PII in AI context; demo records flagged |
| PayPal Secrets | Only in backend `.env`; never in frontend, logs, or AI context |
| Live Payments | `ALLOW_LIVE_PAYMENTS=false` interlock; Sandbox base URL enforced |

## Deployment Notes

- **Single-container**: Backend serves built frontend from `/frontend/dist`
- **SQLite**: File-based (`paypilot.db`); WAL mode for concurrent reads
- **Env**: All config via environment variables (`.env` file)
- **Process**: Uvicorn + 1 worker (demo); add Gunicorn for production
- **HTTPS**: Terminate at reverse proxy (nginx, Caddy, Cloudflare)

## Extensibility Points

| Extension | Location |
|-----------|----------|
| New AI provider | `app/services/ai.py` → subclass `AIProvider` |
| New PayPal webhook | `app/routers/payments.py` + `app/services/paypal.py` |
| New report format | `app/routers/reports.py` |
| New dashboard metric | `app/services/analytics.py` |
| Auth (if added) | `app/deps.py` + middleware in `main.py` |