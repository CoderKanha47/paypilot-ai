# PayPilot AI — Security Documentation

## Threat Model & Scope

**In Scope (MVP):**
- PayPal Sandbox payment flows (Orders v2, OAuth 2.0)
- AI-assisted transaction analysis
- Local SQLite data storage
- Single-user demo deployment

**Out of Scope (MVP):**
- Multi-user authentication/authorization
- Production PCI-DSS compliance
- Real-money (live) payment processing
- High-availability / disaster recovery
- Advanced threat detection

## Security Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRUST BOUNDARIES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐     HTTPS/TLS      ┌─────────────┐                 │
│  │ BROWSER │ ◄─────────────────► │  BACKEND    │                 │
│  │ (UNTRUSTED)                   │  (TRUSTED)  │                 │
│  └─────────┘                     └──────┬──────┘                 │
│         │                               │                        │
│         │  PayPal JS SDK                │  OAuth 2.0             │
│         │  (client-id only)             │  (client-secret)       │
│         ▼                               ▼                        │
│  ┌─────────────────┐          ┌─────────────────┐               │
│  │ PAYPAL SANDBOX  │◄────────►│  AI PROVIDER    │               │
│  │ (EXTERNAL)      │  HTTPS   │  (EXTERNAL)     │               │
│  └─────────────────┘          └─────────────────┘               │
│                                                                  │
│  ┌─────────────────┐                                            │
│  │  SQLITE DB      │                                            │
│  │  (LOCAL FILE)   │                                            │
│  └─────────────────┘                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Secrets Management

| Secret | Location | Exposure |
|--------|----------|----------|
| `PAYPAL_CLIENT_SECRET` | Backend `.env` only | Never in frontend, logs, AI context, DB |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Backend `.env` only | Never in frontend, logs (redacted), AI context |
| PayPal OAuth access token | Backend memory (cached) | Never persisted, auto-refreshed |
| Database credentials | N/A (SQLite file perms) | File-system only |

**Rules:**
- `.env` is git-ignored (`.gitignore`)
- `.env.example` documents required variables without values
- All secret access via `Settings` (Pydantic) — single source of truth
- Structured logging redacts keys matching: `authorization`, `client_secret`, `api_key`, `secret`, `password`, `token`

## PayPal Integration Security

### OAuth 2.0 Client Credentials
- Token acquired at startup, cached with 60s refresh margin
- On 401/403: token invalidated, one retry with fresh token
- Token never logged (redacted in structured logs)
- Base URL validated: Sandbox requires `api-m.sandbox.paypal.com`

### Order Creation
- Server-side only: `POST /v2/checkout/orders` with `intent=CAPTURE`
- Amount/currency validated before network call (integer minor units)
- `custom_id`/`invoice_id` = customer reference for reconciliation
- `application_context`: branded, no shipping, `user_action=PAY_NOW`

### Capture & Verification
- Only orders with **local record** can be captured (ownership check)
- Capture response validated:
  - `order_id` matches request
  - `amount_minor` matches local record
  - `currency` matches local record
- Idempotent: `ORDER_ALREADY_CAPTURED` (HTTP 422) returns existing record
- Failed captures (DECLINED/FAILED/PENDING) recorded with reason

### Browser Trust Model
- **Zero trust** for browser-reported payment status
- PayPal JS SDK renders approval UI only
- `onApprove` callback sends `orderID` to backend for capture
- Backend re-verifies with PayPal before any state change

## AI Provider Security

### Data Minimization
- Context sent to AI includes:
  - Aggregated totals (pre-computed in backend)
  - ≤8 recent transaction refs (id, order_id, amount, status, description, date)
  - ≤8 pending/failed/needs-attention refs
  - Monthly trend aggregates
- **Excluded**: Payer emails, full descriptions, customer notes, raw PayPal responses

### Response Validation
- Model output must be valid JSON with schema: `{answer, facts[], recommendations[], references[], confidence}`
- References filtered to only known transaction/order IDs from context
- Full response scanned for leaked secrets (PayPal secret, AI keys)
- On validation failure: one corrective retry with stricter prompt
- Demo mode responses explicitly labelled

### Provider Isolation
- Each provider: separate class, own HTTP client, own timeout
- No provider can execute actions (no tools, no function calling)
- Timeout enforced (default 30s)
- Retryable vs non-retryable errors distinguished

## Data Protection

### SQLite
- WAL mode for concurrent access safety
- File permissions: rely on OS (chmod 600 recommended for production)
- No encryption at rest (MVP) — document for production

### PII Handling
- Customer reference stored (merchant-provided, not PayPal PII)
- No payer name/email/address stored from PayPal
- `payer_email` extracted only as `account_id` (non-PII) for audit
- AI context excludes customer_reference beyond 40-char truncation

### Export Data
- CSV/JSON exports include all stored fields
- `is_demo_record` flag included for transparency
- Amounts as decimal strings with currency — never summed cross-currency

## Network Security

### CORS
- `CORS_ORIGINS` env var (default: `http://localhost:5173,http://127.0.0.1:5173`)
- No credentials (`allow_credentials=False`)
- Methods: `GET, POST, OPTIONS`
- Headers: `Content-Type, X-Requested-With`

### Headers (All Responses)
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store (API) / no-cache (SPA)
```

### Request Limits
- Max request body: 1 MB (`MAX_REQUEST_BYTES`)
- Rate limiting: sliding window per client IP
  - Create order: 30/min
  - Capture/cancel: 60/min
  - AI chat: 15/min

## Live Payment Interlock

```python
# config.py — enforced at Settings validation
if paypal_mode == "live" and not allow_live_payments:
    raise ValueError("PAYPAL_MODE=live blocked. Set ALLOW_LIVE_PAYMENTS=true only if you genuinely intend to move real money.")
if paypal_mode == "sandbox" and "sandbox" not in paypal_base_url:
    raise ValueError("Sandbox mode requires Sandbox base URL.")
if paypal_mode == "live" and "sandbox" in paypal_base_url:
    raise ValueError("Live mode cannot point at Sandbox endpoint.")
```

- Default: `PAYPAL_MODE=sandbox`, `ALLOW_LIVE_PAYMENTS=false`
- Production deployment **must** explicitly opt in to live
- Hackathon demo: Sandbox only

## Known Vulnerabilities & Mitigations (MVP)

| Issue | Severity | Mitigation |
|-------|----------|------------|
| No authentication | High | Documented; not for public multi-user deployment |
| SQLite file access | Medium | OS perms; not for shared hosting |
| In-process rate limit | Low | Resets on restart; use Redis for prod |
| No CSP/HSTS | Low | Add via reverse proxy |
| No audit logging | Low | Structured logs capture API calls |
| Demo mode confusion | Medium | Explicit badges, notices, `is_demo_record` flag |

## Production Hardening (Post-MVP)

1. **Authentication**: Add OAuth2/OIDC (Auth0, Clerk, or custom JWT)
2. **Authorization**: Row-level security on transactions
3. **Database**: Migrate to PostgreSQL with row-level security
4. **Secrets**: Use Vault/AWS Secrets Manager/GCP Secret Manager
5. **Rate Limiting**: Redis-backed distributed limiter
6. **Monitoring**: Sentry/OpenTelemetry + alerting
7. **CSP/HSTS**: Configure at reverse proxy
8. **PayPal Webhooks**: Replace polling with verified webhooks
9. **Backup**: Automated SQLite/PostgreSQL backups with encryption
10. **Penetration Test**: Before any real-money deployment

## Incident Response

1. **Secret Rotation**: Rotate `PAYPAL_CLIENT_SECRET`, AI keys immediately if exposed
2. **PayPal**: Revoke Sandbox app credentials in Developer Dashboard
3. **Database**: Restore from backup; verify `is_demo_record` integrity
4. **Logs**: Structured JSON logs enable SIEM ingestion

## Compliance Notes

- **PCI-DSS**: Not applicable (PayPal hosts payment fields via JS SDK; no card data touches our servers)
- **GDPR**: Minimal personal data (customer_reference only); no tracking cookies
- **SOC2**: Not certified (MVP)
- **PayPal Terms**: Sandbox use only; no production data in Sandbox

## Security Contacts

- Project maintainer: (add for competition submission)
- PayPal security: https://www.paypal.com/security
- AI provider security: respective vendor portals