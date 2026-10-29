# PayPilot AI — Technical Report

## Executive Summary

PayPilot AI is a complete, functional payment operations dashboard built for the PayPal AI Hackathon. It integrates the PayPal Sandbox (Orders v2 API, OAuth 2.0) for real payment workflows and a swappable AI provider layer (OpenAI, Anthropic, OpenAI-compatible, or a labelled demo engine) for grounded payment insights. The application demonstrates a coherent end-to-end workflow: create payment request → PayPal Sandbox approval → server-side capture & verification → AI-assisted analysis of transaction history.

## Technology Choices & Rationale

| Layer | Choice | Why |
|-------|--------|-----|
| **Backend Framework** | FastAPI | Async-native, automatic OpenAPI docs, Pydantic integration, type-safe |
| **Language** | Python 3.12 | Mature payments/AI ecosystem, Decimal for money, excellent tooling |
| **Database** | SQLite + SQLAlchemy | Zero-config local dev, WAL mode for concurrency, file-based portability |
| **PayPal Client** | HTTPX + custom service | Official REST API (no SDK dependency), token caching, full validation |
| **AI Providers** | Pluggable abstraction | Swappable (OpenAI/Anthropic/Ollama/Groq/demo), JSON mode, secret safety |
| **Frontend Framework** | React 18 + TypeScript | Component model, type safety, vast ecosystem |
| **Build Tool** | Vite | Fast HMR, optimized production builds, simple config |
| **Styling** | Tailwind CSS | Utility-first, consistent design system, small bundle |
| **Charts** | Recharts | React-native, declarative, responsive |
| **PayPal Checkout** | Official JS SDK | PCI-compliant, hosted fields, Sandbox-ready |

## Key Implementation Details

### PayPal Integration (Server-Side Authority)

- **Order Creation**: `POST /v2/checkout/orders` with `intent=CAPTURE`, branded `application_context`, `custom_id`/`invoice_id` for reconciliation
- **OAuth 2.0**: Client credentials grant, token cached until 60s before expiry, automatic 401 retry
- **Capture**: `POST /v2/checkout/orders/{id}/capture` — idempotent (handles `ORDER_ALREADY_CAPTURED`)
- **Verification**: Every capture response validated for `order_id`, `amount_minor`, `currency` match before persistence
- **Ownership**: Only orders created by this app (local record exists) can be captured
- **Browser Trust**: Client-reported status **never** trusted; all state transitions server-verified

### Money Arithmetic (Zero Float)

```python
# Internal: integer minor units (cents for USD)
amount_minor = 2500  # $25.00

# Arithmetic: pure integer
total = sum(row.amount_minor for row in completed_rows)

# Display: Decimal only at edge
from decimal import Decimal
display = Decimal(amount_minor).scaleb(-2)  # 25.00
```

- `money.py` provides `parse_amount_to_minor()`, `format_amount()`, `sum_minor()`, `allocate_minor()`
- Zero-decimal currencies (JPY, KRW, etc.) handled via `minor_exponent()`
- All tests assert exact integer equality

### AI Assistant (Grounded, Not Generative)

**Pipeline:**
1. **Retrieve** — All transactions from SQLite (no vector search needed for MVP scale)
2. **Compute** — Every total calculated in backend Python (integer math)
3. **Minimize** — Context JSON includes only aggregates + ≤8 recent/pending/failed refs
4. **Prompt** — System prompt enforces: no arithmetic, no actions, facts vs recommendations, 140-word limit
5. **Validate** — Response must be JSON with required schema; references filtered to known IDs; secrets scanned
6. **Label** — Demo mode responses carry explicit notice; live mode tagged with provider/model/latency

**Providers:**
- `demo` — Deterministic rule engine, same context, labelled output
- `openai` — `gpt-4o-mini` (default), JSON mode, low temperature
- `anthropic` — `claude-3-5-haiku-latest`
- `openai_compatible` — Any `/v1/chat/completions` endpoint (Ollama, LM Studio, Groq, Together)

### Demo Mode (Honest Simulation)

When `PAYPAL_CLIENT_ID`/`SECRET` absent:
- `DemoCheckout` simulates order create/capture with `mode="demo"`, `is_demo_record=True`
- UI shows "DEMO CHECKOUT" badge; all API responses include `notice` field
- AI provider falls back to `DemoAIProvider` with "Demo mode" notice
- Settings page shows readiness checks with clear guidance
- **Never** presented as real Sandbox activity

## API Design

- **RESTful** with typed Pydantic request/response models
- **Structured errors**: `{code, message, errors?, paypal_error?, retry_after?}`
- **Rate limiting**: Sliding window per IP (stricter on money endpoints)
- **CORS**: Configured origins only, no credentials
- **Request size limit**: 1 MB
- **Security headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`

## Testing Strategy

- **233 unit tests** — all passing, mocked external services
- **Coverage areas**:
  - Health/config endpoints
  - Dashboard metrics & monetary calculations
  - Transaction persistence & queries
  - Payment creation/capture/cancel/sync (mocked PayPal)
  - AI context construction & response validation
  - Demo mode behavior
  - CSV/JSON exports
  - Malformed PayPal/API responses
- **No external dependencies** in test suite (no real PayPal/AI calls)

## Competition Requirements Mapping

| Requirement | Implementation |
|-------------|----------------|
| PayPal Developer Platform + Sandbox | `app/services/paypal.py` — Orders v2, OAuth 2.0, Sandbox base URL |
| Real AI model integration | `app/services/ai.py` — OpenAI/Anthropic/OpenAI-compatible providers |
| PayPal central to product | Payment creation/capture is core workflow; dashboard/assistant derive from it |
| Functional interactive app | Full React SPA with working PayPal checkout flow |
| Newly created for competition | Fresh codebase, no reused production components |
| Public source repository | Ready for GitHub/GitLab/Bitbucket push |
| Open-source license | MIT (see LICENSE) |
| Complete setup instructions | README.md + .env.example + ARCHITECTURE.md |
| Working demo | Local dev (README) + Docker-compose for deployment |
| YouTube demo <3 min | DEMO_SCRIPT.md with timed walkthrough |
| Clear project description | README.md + Devpost description in SUBMISSION_CHECKLIST.md |

## Known Limitations (MVP Scope)

1. **No authentication** — Single-user demo; documented in SECURITY.md
2. **SQLite only** — Not suitable for multi-user production without migration
3. **In-process rate limiter** — Resets on restart; use Redis for production
4. **No PayPal webhooks** — Polling via `/api/payments/order/{id}` instead
5. **No refund/dispute handling** — MVP captures only
6. **Demo AI only without API keys** — Real model requires `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
7. **No multi-currency aggregation** — Amounts never summed across currencies
8. **No production hardening** — CSP, HSTS, secret rotation, audit logging omitted

## Performance Characteristics (Demo Scale)

| Operation | Typical Latency |
|-----------|-----------------|
| Dashboard load | ~50ms (SQLite + compute) |
| Payment create (demo) | ~10ms |
| Payment create (Sandbox) | ~800-1500ms (network) |
| Payment capture (Sandbox) | ~1000-2000ms (network) |
| AI assistant (demo) | ~5ms |
| AI assistant (OpenAI) | ~1500-3000ms |
| CSV export (1000 rows) | ~20ms |

## Deployment Checklist

- [ ] Set `APP_ENV=production`
- [ ] Set `SEED_DEMO_DATA=false`
- [ ] Configure real `PAYPAL_CLIENT_ID`/`SECRET` (Sandbox)
- [ ] Configure `AI_PROVIDER` + API key
- [ ] Set `CORS_ORIGINS` to production frontend URL
- [ ] Use reverse proxy (nginx/Caddy) with HTTPS
- [ ] Run behind Gunicorn: `gunicorn -k uvicorn.workers.UvicornWorker app.main:app`
- [ ] Set up SQLite backup strategy (`.db` + `.db-wal`)
- [ ] Monitor logs (JSON output in production)

## Future Enhancements

- User authentication (OAuth2/OIDC)
- PayPal webhooks for async status updates
- Multi-currency wallet view with FX rates
- Recurring payment templates
- Team/workspace multi-tenancy
- Audit log & compliance exports
- Mobile app (React Native)
- PostgreSQL migration for scale