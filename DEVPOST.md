# Devpost Submission — PayPilot AI

## Project Description

### Inspiration

Freelancers and small businesses juggle payment requests, outstanding invoices, and transaction questions across spreadsheets and PayPal's merchant UI. Existing dashboards display data but don't interpret it or recommend actions. I wanted to build a tool that not only shows the numbers but explains them — grounded in real transaction data, with arithmetic computed exactly in code, not hallucinated by an LLM.

### What It Does

PayPilot AI is an AI-powered payment operations dashboard that:

1. **Creates & captures PayPal Sandbox payments end-to-end** — Server-side order creation via Orders v2 API, payer approval in PayPal's hosted checkout, server-side capture with amount/currency re-validation, and transaction persistence with PayPal order/capture IDs for reconciliation.

2. **Answers payment questions with a grounded AI assistant** — "How much did I collect this week?", "Which payments need follow-up?", "Why did this order fail?" — The backend computes every total in integer cents, sends minimized context to the LLM, and validates the response schema. Facts, recommendations, and transaction references are rendered as separate UI sections.

3. **Provides actionable insights** — Monthly collection trends, pending follow-ups, failure explanations — clearly separating recorded facts from suggestions.

4. **Exports clean reports** — CSV, JSON, and printable summary with demo-data flags.

5. **Runs honestly in demo mode** — Without any API keys, all features are explorable with clearly-labelled simulated data (`DEMO-ORDER-*`, `is_demo_record=true`, "DEMO CHECKOUT" badges).

### How I Built It

**Backend (FastAPI, Python 3.12):**
- Clean architecture: routers → services → models → schemas
- SQLAlchemy 2.0 + SQLite (WAL mode) for zero-config local dev
- Integer minor-unit arithmetic everywhere (`money.py`) — zero floats
- PayPal service: OAuth 2.0 client credentials, token caching, idempotent capture, ownership verification
- AI provider abstraction: OpenAI, Anthropic, OpenAI-compatible (Groq, Ollama...), plus labelled demo engine
- 237 unit tests, all mocked externals

**Frontend (React 18, TypeScript, Vite):**
- Tailwind CSS for a consistent dark/light design system
- Recharts for dashboard visualizations
- PayPal JS SDK for hosted checkout (PCI-compliant, no card data touches our servers)
- Light/dark mode toggle with localStorage persistence

**Security:**
- Secrets stay in backend `.env` only (git-ignored)
- Sandbox-only enforcement (`ALLOW_LIVE_PAYMENTS=false` interlock)
- CORS locked to configured origins, no credentials
- AI context excludes PII; response validated for schema + secret leaks

### Challenges I Faced

1. **Grounding the AI without hallucination** — Solved by computing ALL totals in the backend first, sending only pre-computed aggregates to the model, and validating the JSON response against a strict schema with reference filtering.

2. **PayPal idempotency** — Added `PayPal-Request-Id` headers on create/capture, stable UUID per logical operation stored with the transaction, reused on retry. Duplicate capture safely returns `already_captured: true`.

3. **Honest demo mode** — Ensured every simulated record carries `mode="demo"`, `is_demo_record=true`, API responses include `notice` fields, and UI shows explicit badges. The AI fallback is a deterministic rule engine, also labelled.

4. **Docker volume hiding code (unverified)** — Fixed by mounting the named volume only at `/app/data` for SQLite persistence, not over the entire `/app`. Docker runtime was not verified in the audit environment.

### What I Learned

- How to properly integrate PayPal Orders v2 with server-side authority (zero browser trust)
- Building a swappable AI provider layer with validation and safety rails
- Integer minor-unit arithmetic for exact financial computations
- The importance of clear demo labelling for hackathon submissions

### What's Next

- User authentication (OAuth2/OIDC) for multi-user deployments
- PayPal webhooks for async status updates (replace polling)
- PostgreSQL migration with row-level security
- Multi-currency wallet view with FX rates
- Team/workspace multi-tenancy

---

## Built With

- Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, HTTPX, Pydantic
- React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide React
- PayPal Orders v2 REST API, PayPal JavaScript SDK
- Groq (OpenAI-compatible) — `openai/gpt-oss-120b`
- OpenAI, Anthropic, OpenAI-compatible provider abstraction
- Docker, docker-compose, Uvicorn
- Pytest (237 tests)

---

## Tools Used

### PayPal Developer Platform

| Component | How It's Used |
|-----------|---------------|
| **Sandbox OAuth 2.0** | Client credentials grant (`client_id` + `client_secret`) to obtain access tokens for all API calls. Token cached with 60s refresh margin; automatic retry on 401. |
| **Orders v2 API — Create** | `POST /v2/checkout/orders` with `intent=CAPTURE`, branded `application_context`, `custom_id`/`invoice_id` for reconciliation. Called server-side only. |
| **Orders v2 API — Capture** | `POST /v2/checkout/orders/{id}/capture` — idempotent (handles `ORDER_ALREADY_CAPTURED` by re-fetching). Called server-side only after payer approval. |
| **Orders v2 API — Get** | `GET /v2/checkout/orders/{id}` for sync/status polling. |
| **PayPal JS SDK** | Browser-only checkout UI (`@paypal/paypal-js`). Loads with public `client-id` from backend response. Renders hosted approval flow in iframe/modal. **No secret touches the browser.** |
| **Sandbox Base URL** | All calls target `https://api-m.sandbox.paypal.com`. Enforced by config validation (`PAYPAL_MODE=sandbox` requires sandbox URL). |
| **Sandbox Buyer Account** | Test Personal account from Developer Dashboard → Testing Tools → Sandbox Accounts. Used to approve payments in the hosted checkout. |

### AI Provider — Groq (OpenAI-Compatible)

| Setting | Value |
|---------|-------|
| **Provider** | `openai_compatible` (any OpenAI-shaped `/v1/chat/completions` endpoint) |
| **Base URL** | `https://api.groq.com/openai/v1` |
| **Model ID** | `openai/gpt-oss-120b` |
| **API Key** | Groq API key (`gsk_...`) via `AI_API_KEY` |
| **Timeout** | 30s (configurable via `AI_TIMEOUT_SECONDS`) |
| **Max Tokens** | 700 (configurable via `AI_MAX_TOKENS`) |
| **Temperature** | 0.1 (low for deterministic, grounded output) |
| **Response Format** | JSON mode (`response_format: {"type": "json_object"}`) |

### How the AI Is Used (Precisely)

1. **Backend computes ALL arithmetic** — Every total (sums, averages, trends, success rates) is calculated in Python using **integer minor units** (cents) before any model call. The model **never does math**.

2. **Context minimization** — The prompt sent to the model includes only:
   - Pre-computed aggregates (totals, counts, monthly series)
   - ≤8 recent transaction references (id, order_id, amount, status, description, date)
   - ≤8 pending/failed/needs-attention references
   - No PII (no payer emails, no full customer notes)

3. **Structured response validation** — Model output must be valid JSON with schema:
   ```json
   {
     "answer": "string",
     "facts": ["string"],
     "recommendations": ["string"],
     "references": ["transaction_id"],
     "confidence": "high|medium|low"
   }
   ```
- References filtered to only known transaction IDs from context
    - Full response scanned for leaked secrets (PayPal secret, AI keys)
    - On validation failure: one corrective retry with stricter prompt

4. **Clear labelling** — Every response carries:
   - `provider`: `"groq"` (or `"openai"`, `"anthropic"`, `"demo"`)
   - `mode`: `"live"` (real model) or `"demo"` (deterministic engine)
   - `latency_ms`: actual call duration
   - `disclaimer`: "Recommendations are suggestions, not financial advice."

5. **Demo fallback** — If no API key configured, `DemoAIProvider` returns deterministic answers from the same context, explicitly labelled `mode="demo"`.

### Other Supported AI Providers (Not Used in Verified Live Test)

| Provider | Config | Model Default |
|----------|--------|---------------|
| OpenAI | `AI_PROVIDER=openai`, `OPENAI_API_KEY` | `gpt-4o-mini` |
| Anthropic | `AI_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` | `claude-3-5-haiku-latest` |
| OpenAI-Compatible (Ollama, LM Studio, Together, etc.) | `AI_PROVIDER=openai_compatible`, `AI_BASE_URL`, `AI_API_KEY` (optional), `AI_MODEL` | `llama3.1` |
| Demo | `AI_PROVIDER=demo` (default) | Deterministic rule engine |

---

**How This Was Built**

This project was built with AI coding assistance (OpenCode). I directed the design, reviewed all code changes, and ran the live PayPal Sandbox and Groq integration tests on 2026-11-04. The full create → approve → capture flow and the AI assistant were verified live on 2026-11-04 against the real PayPal Sandbox and Groq's `openai/gpt-oss-120b` model.

**Runtime tools:** PayPal Sandbox (OAuth 2.0, Orders v2 API, JS SDK) and Groq (`openai/gpt-oss-120b` via OpenAI-compatible endpoint).  
**Development tools:** OpenCode with AI coding models.  
All totals are computed in backend code with integer arithmetic; the model only explains and recommends from minimized data.