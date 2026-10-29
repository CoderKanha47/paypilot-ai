# PayPilot AI

**Smarter payments. Clearer decisions. Less busywork.**

An AI-powered payment operations dashboard built on the PayPal Sandbox for freelancers, independent service providers, and small businesses.

## Features

- **PayPal Sandbox Integration** — Server-created orders, payer approval via PayPal's hosted checkout, server-side capture and verification using Orders v2 API and OAuth 2.0 client credentials
- **AI Payment Assistant** — Grounded answers about your payment data using real transaction records (OpenAI, Anthropic, or any OpenAI-compatible endpoint; demo mode included)
- **Dashboard** — Total captured, pending requests, failed/declined counts, success rate, monthly collection chart, status distribution
- **Payment Creation** — Amount, currency, description, customer reference; validation; PayPal Sandbox approval and capture flow
- **Transaction History** — Search, date/status filters, detail view with PayPal order/capture references
- **Reports** — CSV/JSON exports, printable summary
- **Demo Mode** — Fully functional UI exploration without PayPal credentials (clearly labelled)
- **Security** — Secrets stay on backend, no PII sent to AI, Sandbox-only enforcement

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- PayPal Developer account (for Sandbox credentials)
- AI provider API key (optional — demo mode works out of the box)

### Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e .
cp .env.example .env
# Edit .env with your credentials (see Configuration below)
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Configuration

Copy `.env.example` to `.env` in the project root and fill in:

```ini
# PayPal Sandbox (get from https://developer.paypal.com → Apps & Credentials → Sandbox)
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CURRENCY=USD

# AI Provider (optional — defaults to demo mode)
AI_PROVIDER=openai          # or: anthropic, openai_compatible, demo
OPENAI_API_KEY=sk-...       # if using OpenAI
ANTHROPIC_API_KEY=sk-...    # if using Anthropic

# Demo data
SEED_DEMO_DATA=true
```

**Never commit `.env` — it's git-ignored.**

## Architecture

- **Backend**: FastAPI, SQLAlchemy + SQLite, HTTPX, Pydantic
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Recharts
- **Payments**: PayPal Orders v2 REST API (server-side), PayPal JS SDK (browser checkout)
- **AI**: Swappable provider abstraction (OpenAI, Anthropic, OpenAI-compatible, demo)

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

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

## Testing

```bash
cd backend
pytest tests/ -v
```

All 233 tests pass (unit tests with mocked external services).

## Competition Submission

This project satisfies the PayPal AI Hackathon requirements:

- ✅ PayPal Developer Platform + Sandbox integration (central to product)
- ✅ Real AI model integration (OpenAI/Anthropic/OpenAI-compatible)
- ✅ Functional interactive application (not a prototype)
- ✅ Newly created for the competition
- ✅ Public source repository ready
- ✅ MIT License
- ✅ Complete setup instructions
- ✅ Working demo (local + deployable)
- ✅ Demo video script under 3 minutes
- ✅ Clear project description

## License

MIT — see [LICENSE](LICENSE).

## Demo Video Script

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) for a 3-minute walkthrough.

---

**Built for the PayPal AI Hackathon.** Not production-ready for real customer funds — authentication is omitted for the demo.