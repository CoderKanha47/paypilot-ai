# Tools Used — PayPilot AI

## PayPal Developer Platform

| Component | How It's Used |
|-----------|---------------|
| **Sandbox OAuth 2.0** | Client credentials grant (`client_id` + `client_secret`) to obtain access tokens for all API calls. Token cached with 60s refresh margin; automatic retry on 401. |
| **Orders v2 API — Create** | `POST /v2/checkout/orders` with `intent=CAPTURE`, branded `application_context`, `custom_id`/`invoice_id` for reconciliation. Called server-side only. |
| **Orders v2 API — Capture** | `POST /v2/checkout/orders/{id}/capture` — idempotent (handles `ORDER_ALREADY_CAPTURED` by re-fetching). Called server-side only after payer approval. |
| **Orders v2 API — Get** | `GET /v2/checkout/orders/{id}` for sync/status polling. |
| **PayPal JS SDK** | Browser-only checkout UI (`@paypal/paypal-js`). Loads with public `client-id` from backend response. Renders hosted approval flow in iframe/modal. **No secret touches the browser.** |
| **Sandbox Base URL** | All calls target `https://api-m.sandbox.paypal.com`. Enforced by config validation (`PAYPAL_MODE=sandbox` requires sandbox URL). |
| **Sandbox Buyer Account** | Test Personal account from Developer Dashboard → Testing Tools → Sandbox Accounts. Used to approve payments in the hosted checkout. |

## AI Provider — Groq (OpenAI-Compatible)

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

**No other tools or services were used.** The application uses only the PayPal Developer Platform (Sandbox) and the Groq OpenAI-compatible endpoint for the verified live test. All totals are computed in backend code with integer arithmetic; the model only explains and recommends from minimized data.