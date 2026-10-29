# PayPilot AI — Resume-Ready Project Description

## One-Liner
**AI-powered PayPal payment operations dashboard** — server-side PayPal Sandbox order/capture flow + grounded LLM assistant that answers payment questions from real transaction data.

## Problem
Freelancers and small businesses juggle payment requests, outstanding invoices, and transaction questions across spreadsheets and PayPal's merchant UI. Existing dashboards display data but don't interpret it or recommend actions.

## Solution
PayPilot AI unifies payment operations and intelligence in one dashboard:
- **PayPal Sandbox integration** (Orders v2, OAuth 2.0): create payment request → payer approves in PayPal checkout → server captures & verifies → persists transaction
- **Grounded AI assistant**: "How much did I collect this week?" / "Which payments need follow-up?" / "Why did this order fail?" — backend computes all totals in integer cents, sends minimized context to LLM, validates response schema
- **Transaction history** with search, filters, PayPal order/capture references
- **Reports**: CSV/JSON exports, printable summary

## My Role
Solo full-stack engineer: architecture, backend (FastAPI, SQLAlchemy, PayPal REST), frontend (React, TypeScript, Tailwind, Recharts), AI integration (provider abstraction, prompt engineering, validation), testing (233 unit tests), documentation, Docker deployment.

## Technical Highlights

| Area | Achievement |
|------|-------------|
| **Payments** | Server-created orders, zero browser trust, idempotent capture, ownership verification, amount/currency re-validation |
| **Money** | Zero-float arithmetic: all sums/comparisons in integer minor units; Decimal only at display edge |
| **AI** | Swappable providers (OpenAI, Anthropic, OpenAI-compatible, demo); JSON mode; response validation (schema, reference filtering, secret scanning); deterministic demo fallback |
| **Security** | Secrets in backend only; CORS locked down; Sandbox-only interlock; structured logging with redaction; rate limiting |
| **Testing** | 233 tests, all mocked externals; covers payments, AI context, monetary math, exports, error handling |
| **Architecture** | Clean separation: routers → services → models; dependency injection; typed Pydantic schemas throughout |

## Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite (WAL), HTTPX, Pydantic, Pytest
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide icons
- **Payments**: PayPal Orders v2 REST API, PayPal JS SDK (browser checkout)
- **AI**: OpenAI Chat Completions, Anthropic Messages, OpenAI-compatible endpoints
- **DevOps**: Docker, docker-compose, Gunicorn/Uvicorn

## Metrics
- **233 passing tests** (0 external dependencies in test suite)
- **~40 Python files**, **~15 React components**, **~8 API endpoints**
- **Sub-100ms dashboard load** (SQLite + integer math)
- **Docker image** ~200MB (multi-stage build)

## Links
- **Repo**: `https://github.com/<username>/paypilot-ai`
- **Demo Video**: `https://youtu.be/<video-id>` (2:45)
- **Docs**: `README.md`, `ARCHITECTURE.md`, `TECHNICAL_REPORT.md`, `SECURITY.md`

## Interview Talking Points

**Q: How do you ensure the AI doesn't hallucinate financial numbers?**
A: The backend computes every total (sums, averages, trends) in Python using integer minor units before sending context to the LLM. The model only receives pre-computed aggregates and a few transaction references — it never does arithmetic. Response validation enforces schema and filters references to known IDs.

**Q: Why server-side capture instead of client-side?**
A: The browser cannot be trusted. A malicious user could spoof a "success" callback. Our backend re-verifies with PayPal (`GET /v2/checkout/orders/{id}` then `POST .../capture`), validates the returned amount/currency against the local record, and only then marks the transaction completed.

**Q: How does demo mode work without PayPal credentials?**
A: `DemoCheckout` simulates the same normalized response shape as `PayPalService`. Records are persisted with `mode="demo"` and `is_demo_record=True`. Every API response includes a `notice` field; the UI shows "DEMO CHECKOUT" badges. The AI falls back to a deterministic rule engine using the same context — also explicitly labelled.

**Q: What would you change for production?**
A: Add authentication (OAuth2/OIDC), migrate to PostgreSQL with row-level security, replace in-process rate limiter with Redis, add PayPal webhooks for async status, CSP/HSTS at reverse proxy, secret rotation via Vault, audit logging, automated backups.

**Q: How do you handle multi-currency?**
A: Amounts stored as integer minor units + ISO-4217 currency. Arithmetic only within same currency (enforced by `sum_minor` filter). Dashboard shows primary currency totals + separate "other currencies" breakdown. Exports include currency column with note: "sum only within a single currency."