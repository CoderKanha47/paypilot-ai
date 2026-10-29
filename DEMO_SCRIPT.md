# PayPilot AI — Demo Video Script (Under 3 Minutes)

## Target: PayPal AI Hackathon Submission Video
**Duration**: ~2 minutes 45 seconds  
**Format**: Screen recording + voiceover  
**Resolution**: 1920x1080 minimum  

---

### 0:00–0:15 — Introduction (15s)
**Visual**: Terminal showing `docker compose up` or `uvicorn` + `npm run dev` starting  
**Voiceover**:  
"PayPilot AI — an AI-powered payment operations dashboard built for the PayPal AI Hackathon. It integrates the PayPal Sandbox for real payment workflows and a grounded AI assistant for payment insights. Let me walk you through the complete flow."

---

### 0:15–0:35 — Dashboard Overview (20s)
**Visual**: Browser at `http://localhost:5173` — Overview page  
**Actions**:
- Show KPI cards: Total Captured, Awaiting Payment, Failed/Declined, Success Rate
- Hover monthly collections chart (Recharts area chart)
- Show status distribution donut chart
- Point out "SANDBOX CHECKOUT" badge (or "DEMO CHECKOUT" if no creds)
- Show recent transactions table

**Voiceover**:  
"Every metric here is computed from the SQLite database — no hardcoded numbers. The charts use real transaction data. The Sandbox badge confirms we're connected to PayPal's test environment."

---

### 0:35–1:15 — Create & Approve a Payment (40s)
**Visual**: Navigate to "New Payment" page  
**Actions**:
1. Fill form: Amount `49.99`, Currency `USD`, Description `Logo design — Acme Corp`, Reference `INV-2026-042`
2. Click "Create PayPal order" — show loading, then PayPal buttons appear
3. Click "PayPal" button → Sandbox checkout opens in modal
4. Log in with Sandbox buyer account (or use test card: `4111 1111 1111 1111`)
5. Approve payment
6. Back in app: "Verifying and recording..." → Success panel appears
7. Click "View transaction"

**Voiceover**:  
"The order is created server-side via PayPal Orders v2 API. The payer approves in PayPal's own hosted checkout — we never see card data. On approval, our backend captures the order, re-validates amount and currency against our record, and persists the transaction. This is a real Sandbox transaction."

---

### 1:15–1:45 — Transaction History & Detail (30s)
**Visual**: Transaction detail page (from "View transaction")  
**Actions**:
- Show PayPal Order ID, Capture ID, status badge (Completed)
- Show amount, currency, description, timestamps
- Click "Transactions" in nav → show search, status filter, date filter
- Demonstrate filtering by "Completed" status

**Voiceover**:  
"Every transaction stores the PayPal order and capture IDs for reconciliation. The history page supports full-text search, status and date filters, and pagination."

---

### 1:45–2:20 — AI Payment Assistant (35s)
**Visual**: Navigate to "AI Assistant" page  
**Actions**:
1. Click suggested question: "How much did I collect this week?"
2. Show response: facts (computed totals), recommendations, confidence
2. Ask: "Which payments are still pending?"
3. Show response with transaction references
4. Ask: "Summarize my recent transactions"
5. Point out "Demo mode" notice (if no AI key) or provider badge

**Voiceover**:  
"The assistant reads real aggregates from your database — all arithmetic is done in the backend using integer math, never by the model. The context sent to the AI is minimized and PII-scrubbed. Responses separate recorded facts from suggestions, and every response carries a disclaimer. Swap in OpenAI or Anthropic by adding an API key."

---

### 2:20–2:40 — Reports & Settings (20s)
**Visual**: Reports page → click "CSV" and "JSON" downloads  
**Actions**:
- Show downloaded CSV opened in spreadsheet
- Show Settings page with readiness checks (PayPal, AI, Demo data, Health)

**Voiceover**:  
"One-click CSV and JSON exports plus a printable summary. The Settings page shows runtime readiness — PayPal configured, AI provider status, demo data presence, and backend health."

---

### 2:40–2:45 — Closing (5s)
**Visual**: Terminal showing `pytest tests/ -v` passing (233 tests)  
**Voiceover**:  
"233 passing tests, zero external dependencies in the test suite. PayPilot AI — smarter payments, clearer decisions, less busywork. Thank you."

---

## Recording Tips

1. **Prepare data**: Seed demo data (`SEED_DEMO_DATA=true`) for charts/history
2. **Sandbox account**: Have buyer credentials ready (or use test card numbers shown in New Payment sidebar)
3. **Browser**: Hide bookmarks bar, use clean profile
4. **Audio**: Record voiceover separately for clarity, then sync
5. **Zoom**: Zoom in on key UI elements (form fields, badges, numbers)
6. **Pacing**: Speak clearly, ~150 words/minute

## Test Card Numbers (Sandbox)
- **Approve**: `4111 1111 1111 1111` (any future expiry)
- **Decline**: `4000 0000 0000 0002`
- **Insufficient funds**: `4000 0000 0000 9995`

## Key Talking Points for Judges

- "PayPal integration is **central** — not a decorative button. The entire workflow depends on it."
- "AI is **grounded** — no hallucinated numbers. Backend computes every total in integer cents."
- "Security: **Secrets never leave the backend**. Browser only sees public client-id."
- "Demo mode is **honest** — clearly labelled, never presented as real Sandbox activity."
- "Built for the hackathon — **233 tests**, clean architecture, ready to extend."