# PayPilot AI

**Smarter payments. Clearer decisions. Less busywork.**

An AI-powered payment operations dashboard built on the PayPal Sandbox for freelancers, independent service providers, and small businesses.

## Features

- **PayPal Sandbox Integration** — Server-created orders, payer approval via PayPal's hosted checkout, server-side capture and verification using Orders v2 API and OAuth 2.0 client credentials
- **AI Payment Assistant** — Grounded answers about your payment data using real transaction records (OpenAI, Anthropic, or any OpenAI-compatible endpoint such as Groq; demo mode included)
- **Dashboard** — Total captured, pending requests, failed/declined counts, success rate, monthly collection chart, status distribution
- **Payment Creation** — Amount, currency, description, customer reference; validation; PayPal Sandbox approval and capture flow
- **Transaction History** — Search, date/status filters, detail view with PayPal order/capture references
- **Reports** — CSV/JSON exports, printable summary
- **Demo Mode** — Fully functional UI exploration without PayPal credentials (clearly labelled)
- **Security** — Secrets stay on backend, no PII sent to AI, Sandbox-only enforcement

## Screenshots

*Placeholder — add screenshots of Overview dashboard, New Payment flow, AI Assistant, Transaction History, Reports, Settings*

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite (WAL), HTTPX, Pydantic |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide icons |
| Payments | PayPal Orders v2 REST API (server-side), PayPal JS SDK (browser checkout) |
| AI | Swappable provider abstraction (OpenAI, Anthropic, OpenAI-compatible, demo) |
| DevOps | Docker, docker-compose, Uvicorn |

## Quick Start

### Prerequisites

- **Python 3.12.x** (3.13+ is NOT supported by `pyproject.toml`)
- **Node.js 20+**
- PayPal Developer account (for Sandbox credentials) — optional for demo mode
- AI provider API key (optional — demo mode works out of the box)

### Exact .env Location

The backend reads `.env` from **two locations** (in priority order):
1. `backend/.env` — project-specific
2. `.env` at **repository root** — shared

Create your `.env` at the **repository root** (same folder as this README). The app will find it.

### Windows (PowerShell)

```powershell
# 1. Clone
git clone https://github.com/<your-username>/paypilot-ai.git
cd paypilot-ai

# 2. Backend
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"          # installs runtime + test deps (pytest)
copy ..\.env.example .env         # creates .env at repo root
# Edit .env with your credentials (see Configuration below)
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd ..\frontend
npm install
npm run dev
```

### macOS / Linux (bash)

```bash
# 1. Clone
git clone https://github.com/<your-username>/paypilot-ai.git
cd paypilot-ai

# 2. Backend
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example .env
# Edit .env with your credentials
.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd ../frontend
npm install
npm run dev
```

### Open the App

- Frontend (Vite dev server): **http://localhost:5173** (proxies `/api/*` to backend)
- Backend API: **http://localhost:8000** (also serves built SPA from `frontend/dist/` if present)
- API health check: `curl http://localhost:8000/api/health`

### Configuration

Edit `.env` at the **repository root** with your credentials:

```ini
# PayPal Sandbox (get from https://developer.paypal.com → Apps & Credentials → Sandbox)
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CURRENCY=USD

# AI Provider (optional — defaults to demo mode)
AI_PROVIDER=openai_compatible      # openai | anthropic | openai_compatible | demo
AI_BASE_URL=https://api.groq.com/openai/v1
AI_API_KEY=gsk_...                 # Groq API key
AI_MODEL=openai/gpt-oss-120b

# Demo data
SEED_DEMO_DATA=true
```

**Never commit `.env` — it's git-ignored.**

### How a Judge Gets Free Credentials

| Service | What You Need | How to Get It |
|---------|---------------|---------------|
| **PayPal Sandbox** | `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | 1. Go to https://developer.paypal.com → Dashboard → Apps & Credentials → Sandbox<br>2. Create App → copy Client ID & Secret |
| **Sandbox Buyer Account** | Test buyer email/password | 1. In Developer Dashboard → Testing Tools → Sandbox Accounts<br>2. Create a "Personal" (buyer) account<br>3. Use its email/password at checkout, or use test card `4111 1111 1111 1111` |
| **Groq (AI)** | `AI_API_KEY` (Groq key), `AI_BASE_URL=https://api.groq.com/openai/v1`, `AI_MODEL=openai/gpt-oss-120b` | 1. Sign up at https://console.groq.com → API Keys → Create Key<br>2. Free tier includes generous daily limits |
| **OpenAI / Anthropic (alternative)** | `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | Standard API keys from respective platforms |

### Docker (Unverified — Daemon Not Available in Audit)

```bash
docker compose up --build
# Then open http://localhost:8000
```

**Note:** The Docker build was fixed in code (copies `backend/README.md`, uses `uvicorn`, mounts data volume at `/app/data`), but **the Docker runtime was NOT verified** because no Docker daemon was available in the audit environment. Run `docker compose build && docker compose up -d && curl -f http://localhost:8000/api/health` to verify locally.

### Demo Mode

If **no PayPal credentials** are configured, the app runs in **Demo Mode**:
- Payment creation/capture is simulated locally (`DEMO-ORDER-*`, `DEMO-CAP-*`)
- All records marked `mode="demo"`, `is_demo_record=true`
- UI shows "DEMO CHECKOUT" badges; API responses include `notice` field
- AI assistant uses a deterministic rule engine (also labelled "Demo mode")
- **No real PayPal Sandbox transaction occurs. No real AI model is called.**

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for component diagrams, data flows, and database schema.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness + dependency check |
| GET | `/api/config` | Public runtime config |
| GET | `/api/dashboard` | Aggregated metrics + charts |
| GET | `/api/transactions` | Filtered transaction list |
| GET | `/api/transactions/{id}` | Transaction detail |
| POST | `/api/payments/create-order` | Create PayPal order |
| POST | `/api/payments/capture-order` | Capture approved order |
| POST | `/api/payments/cancel-order` | Cancel pending order |
| GET | `/api/payments/order/{id}` | Sync order from PayPal |
| POST | `/api/assistant/chat` | Ask AI assistant |
| GET | `/api/assistant/suggestions` | Example questions |
| GET | `/api/reports/transactions.csv` | CSV export |
| GET | `/api/reports/transactions.json` | JSON export |
| GET | `/api/reports/summary` | Printable summary |

## Running Tests

```bash
cd backend
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pytest tests/ -v
```

**Result:** 237 tests pass (includes 4 PayPal idempotency tests). All external services mocked.

## Limitations

- **No authentication** — Single-user demo; not for public multi-user deployment
- **Sandbox only** — `ALLOW_LIVE_PAYMENTS=false` interlock prevents real money
- **Not production-ready** — SQLite, in-process rate limiting, no CSP/HSTS, no audit logging
- **Not financial advice** — AI recommendations are suggestions only; always verify with PayPal
- **Docker not verified** — Build fixed but runtime untested in audit environment

## License

MIT — see [LICENSE](LICENSE).

## Demo Video Script

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for a 3-minute walkthrough.

---

**Built for the PayPal AI Hackathon.** Not production-ready for real customer funds — authentication is omitted for the demo.