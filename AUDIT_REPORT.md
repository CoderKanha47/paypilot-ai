# PayPilot AI - Hackathon Readiness Audit

**Audit date:** 2026-11-04
**Repository:** `D:\Kanha Folder\Projects\PayPal Hackathon`
**Audit mode:** Read-only against source; verification was performed in a clean `git archive` copy at `C:\Users\hermi\AppData\Local\Temp\opencode\paypilot-audit`.
**Audited commit:** `e914a73` (HEAD, 2026-10-29 10:38:41 +0530)
**Environment:** Windows, PowerShell 5.1, Python 3.12.13, Node 24.16.0, npm 11.13.0, Docker CLI 29.8.2 (daemon not running).

> Rule IDs R1-R9 below are the audit checklist headings used in this review. The descriptions are restated so the report is self-contained; findings map by heading even if your brief numbered them differently.

---

## 1. Verdict

**Not submission-ready as-is.**

The application is substantive and the local demo path works: the backend starts without credentials, seeds clearly-labelled demo data, serves a working React SPA, passes all 233 backend tests, builds the frontend, and completes a create -> approve -> capture flow in demo mode.

However, four things block a clean submission:

1. **The advertised Docker path is broken.** `docker compose up --build` cannot succeed as written: the image build fails because `backend/README.md` is not copied before `pip install`, and the runtime command uses `gunicorn`, which is not a dependency.
2. **Submission assets are incomplete.** There is no git remote/public repository, no actual YouTube demo video (only a script and a placeholder URL), and no explicit AI tools statement.
3. **The documented Quick Start fails as written.** `cp .env.example .env` is run after `cd backend`, but `.env.example` exists only at the repository root; `pip install -e .` does not install the test dependencies; and the stated Python range is too broad.
4. **Live PayPal Sandbox and real AI were not verified.** No credentials exist in the repository or environment, so every runtime payment test was demo mode and every assistant answer came from the deterministic demo engine. Claims of "real Sandbox transaction" and "real AI" remain unproven until tested with credentials.

Strongest parts: honest demo labelling, server-side PayPal architecture, amount/ownership revalidation, clear error handling, no committed secrets, and a genuinely broad test suite.

---

## 2. Live vs mocked statement

| Area | What was exercised | Result |
|---|---|---|
| PayPal runtime | No `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` present; no `.env` tracked | **NOT VERIFIED against live PayPal Sandbox.** All order IDs were `DEMO-ORDER-*` and captures `DEMO-CAP-*`. |
| AI runtime | `AI_PROVIDER=demo`; no OpenAI/Anthropic key present | **NOT VERIFIED against a real model.** The assistant returned the deterministic demo engine output with a demo notice. |
| Backend tests | `pytest tests/ -v` with no credentials and no network dependency | **233 passed**; external services are mocked by the suite. |
| Frontend build | `npm install` + `npm run build` | **PASS**; TypeScript check and Vite production build succeeded. |
| Docker | `docker compose config` only; daemon not running | **Compose file is valid, but the image build/runtime is broken by static defects** (reproduced outside Docker; see B1). |

No real money, real payer account, or real model API was used at any point.

---

## 3. R1-R9 checklist

| Rule | Requirement (restated) | Status | Evidence |
|---|---|---|---|
| **R1** | PayPal integration is real and server-side, not a mock | **PASS (code) / NOT VERIFIED (live)** | `backend/app/services/paypal.py:120-176` OAuth2 client-credentials + token cache; `:324` `POST /v2/checkout/orders`; `:331-348` capture + already-captured recovery; sandbox base URL in config. No mock provider in the runtime path. |
| **R2** | AI integration is real and meaningful | **PARTIAL** | Real providers exist for OpenAI, Anthropic, and OpenAI-compatible endpoints (`backend/app/services/ai.py`), with JSON validation and a clearly labelled demo fallback. Default and verified runtime was demo only; no real model call was demonstrated. |
| **R3** | PayPal is central and the product works end to end | **PASS (demo) / NOT VERIFIED (live)** | Verified `POST /api/payments/create-order` -> `POST /api/payments/capture-order` with demo approval; record became `completed` and recapture returned `already_captured: true`. Frontend uses the official PayPal JS SDK and backend-owned order IDs (`frontend/src/components/PayPalCheckout.tsx:100-127`). |
| **R4** | Secrets and security boundaries are sound | **PASS (with documented no-auth caveat)** | No `.env` tracked; `.env` ignored at `.gitignore:2`; secret scan found only placeholders; client secret stays server-side; `/api/config` returns public client ID only; sandbox/live interlock in `backend/app/config.py`; CORS, request-size limit, rate limits, and security headers present. Authentication is intentionally absent and disclosed at `README.md:134`. |
| **R5** | Demo mode is honest, labelled, and usable without credentials | **PASS** | Fresh DB seeded 18 rows, all `mode="demo"` / `is_demo_record=true`; dashboard returned `demo_data_included: true`; create/capture responses carried demo notices; demo order/capture IDs are prefixed `DEMO`; UI shows a mode banner. |
| **R6** | Tests, frontend build, and runnable packaging are healthy | **PARTIAL** | Tests: 233 passed in 5.19s. Frontend: build succeeded. Packaging: Docker build and runtime are broken (B1). No lint script exists. |
| **R7** | Setup and documentation are accurate and reproducible | **FAIL** | Extensive docs exist, but the Quick Start `cp` path fails, Python prerequisite is too broad, `pip install -e .` leaves `pytest` missing, and the Docker success claims are false. See section 5. |
| **R8** | Public open-source submission package is complete | **FAIL** | MIT `LICENSE` present and detectable. But `git remote -v` is empty, no public repository exists, `RESUME_DESCRIPTION.md:45` still has a placeholder video URL, and no AI tools statement was found. |
| **R9** | Original, meaningful work is evidenced | **PARTIAL** | Codebase is substantive and plausibly newly created. Git history is only two bulk commits on the same day (`3efaa70`, then `e914a73` nine minutes later), so incremental progress is not evidenced. This is not an official-rules blocker but is weak for an effort/history check. |

---

## 4. Verified commands and exact results

### Backend dependency install

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Result: `fastapi==0.115.6`, `httpx==0.28.1`, `pydantic==2.10.4`, `pydantic-settings==2.7.1`, `pytest==8.3.4`, `pytest-asyncio==0.25.2`, `SQLAlchemy==2.0.36`, `uvicorn==0.34.0`; Python 3.12.13.

Note: the documented `pip install -e .` omits `pytest`; the `dev` extra is required to run the documented test command.

### Backend tests

```powershell
.venv\Scripts\python.exe -m pytest tests\ -v
```

Exact result:

```text
collected 233 items
233 passed in 5.19s
```

This confirms the repeated "233 tests" claim. The static count of `def test_` functions is 167; parametrization produces the remaining cases.

### Backend startup

```powershell
# from backend/
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --host 127.0.0.1
```

Result: starts without a `.env`; `/api/health` returns HTTP 200:

```json
{"status":"ok","app":"PayPilot AI","version":"1.0.0","environment":"development","database":"connected","paypal_configured":false,"paypal_mode":"disabled","ai_provider":"demo","ai_configured":true}
```

### Endpoint smoke tests

| Endpoint | Result |
|---|---|
| `GET /api/health` | 200, `status: ok` |
| `GET /api/config` | 200, `demo_mode: true`, PayPal not configured, demo notice present |
| `GET /api/dashboard` | 200, 18 seeded transactions, `demo_data_included: true` |
| `GET /api/transactions` | 200, paginated list |
| `GET /api/reports/transactions.csv` | 200, valid CSV with header and demo rows |
| `GET /api/reports/transactions.json` | 200, valid JSON report |
| `POST /api/payments/create-order` (`12.34 USD`) | 200, `mode: demo`, `order_id: DEMO-ORDER-*` |
| `POST /api/payments/create-order` (`-5`) | 422, `Amount must be greater than zero` |
| `POST /api/payments/create-order` (`XYZ`) | 422, `Unsupported currency 'XYZ'` |
| `POST /api/payments/capture-order` (`demo_outcome=approve`) | 200, `status: completed`, `is_demo_record: true` |
| Same capture repeated | 200, `already_captured: true` |
| `POST /api/assistant/chat` | 200, demo answer with facts, recommendations, references, confidence, disclaimer |

### Frontend

```powershell
npm install
npm run build
```

Result: 129 packages installed; `tsc --noEmit && vite build` succeeded; 2197 modules transformed; `dist/index.html` plus hashed CSS/JS emitted. The JS bundle is 642.39 kB (190.32 kB gzip).

### Dev server and SPA

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

Result: Vite served HTTP 200 at `http://127.0.0.1:5173/`; the Vite proxy forwarded `/api/health` to the backend successfully. The backend also served the built SPA at `http://127.0.0.1:8000/` when `frontend/dist` existed.

### Docker

```powershell
docker compose config
```

Result: compose file is syntactically valid. `docker compose config` resolves the `paypilot-data` volume and environment.

```powershell
docker build -t paypilot-audit-test .
```

Result: **NOT EXECUTED** - Docker daemon is not running:

```text
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
```

However, the build failure was reproduced outside Docker by copying only `backend/pyproject.toml` into an empty directory and running the same install step:

```text
OSError: Readme file does not exist: README.md
error: metadata-generation-failed
```

`gunicorn` is also not present in the environment or in `backend/pyproject.toml`:

```text
WARNING: Package(s) not found: gunicorn
```

So B1 is a proven defect, not merely an unverified suspicion.

---

## 5. Blocking issues

### B1 - Docker build and runtime are broken

**Status:** FAIL (high confidence)
**Evidence:**

- `Dockerfile:22-24` copies only `backend/pyproject.toml` and `backend/uv.lock*` to `/app`, then runs `pip install -e .` with a fallback to `pip install .`.
- `backend/pyproject.toml:5` declares `readme = "README.md"`, but `backend/README.md` is not copied into the image.
- Reproduced: `OSError: Readme file does not exist: README.md`.
- `Dockerfile:50` runs `gunicorn`, but `backend/pyproject.toml:8-15` does not include `gunicorn`; `pip show gunicorn` returns not found.
- `docker-compose.yml:32-33` mounts `paypilot-data:/app`, which hides the image's application code on subsequent runs (Docker initializes the volume from the image on first use, but rebuilds can serve stale code).

**Impact:** Both judge paths that mention Docker (`SUBMISSION_CHECKLIST.md:47-49`, `README.md:120`, `TECHNICAL_REPORT.md:111`) are false. A judge who runs `docker compose up --build` will not get a working demo.

**Fix prompt:**

```text
Fix the Docker path in this repo. In Dockerfile, copy backend/README.md together with backend/pyproject.toml and backend/uv.lock before the pip install step. Add a pinned gunicorn dependency to backend/pyproject.toml (and ensure uvicorn[standard] workers are available). In docker-compose.yml, stop mounting the named volume over /app; mount only a dedicated data directory (for example /app/data) and set DATABASE_URL to that path. Verify with: docker compose build && docker compose up -d && curl -f http://localhost:8000/api/health && docker compose down. Do not change application behavior.
```

### B2 - Submission assets are incomplete

**Status:** FAIL
**Evidence:**

- `git remote -v` returns nothing; no public repository is configured.
- `SUBMISSION_CHECKLIST.md:12` marks the public repository as pending (correctly).
- `RESUME_DESCRIPTION.md:45` contains `https://youtu.be/<video-id>` - an unfilled placeholder.
- `SUBMISSION_CHECKLIST.md:16` claims a YouTube video under 3 minutes, but the evidence is only `DEMO_SCRIPT.md`; no video file or URL exists.
- No explicit "AI tools statement" (the official rules ask entrants to name every AI tool/model used and explain how) was found in the repository. `RESUME_DESCRIPTION.md` and `TECHNICAL_REPORT.md` describe the stack but do not present a submission-ready tools statement.

**Impact:** These are hard submission requirements. Without the public repo and video, the project cannot be entered even though the code works locally.

**Fix prompt:**

```text
Prepare the submission assets without changing application code. Create a concise AI_TOOLS_STATEMENT.md listing every AI tool/model/provider used (OpenAI, Anthropic, any OpenAI-compatible endpoint, the deterministic demo engine) and exactly how each is used. Replace the placeholder video URL in RESUME_DESCRIPTION.md with the final YouTube URL only after the video exists. Add a clear "Submission status" section to SUBMISSION_CHECKLIST.md that distinguishes done items from user actions still required: create public GitHub repo, push main, record/upload the <3 minute video, and paste links. Do not claim any item is complete until the link exists.
```

### B3 - Documented Quick Start fails as written

**Status:** FAIL
**Evidence:**

- `README.md:30` changes into `backend/`, then `README.md:35` runs `cp .env.example .env`. `.env.example` exists only at the repository root, so this command fails. (The app does read both `backend/.env` and the root `.env`, so copying the root file to the root works - but the documented command does not.)
- `README.md:34` runs `pip install -e .`, which installs runtime dependencies only. `pytest` is in the `dev` extra (`backend/pyproject.toml:17-22`), so the documented `pytest tests/ -v` at `README.md:103-104` fails in a fresh environment.
- `README.md:22` says "Python 3.12+", but `backend/pyproject.toml:6` requires `>=3.12,<3.13`. Installing on Python 3.13/3.14 is rejected; the audit used 3.12.13.
- `start.bat` correctly checks for `.venv` and `node_modules` but does not create or copy `.env`; that is acceptable for demo mode, but it does not repair the README instructions.

**Impact:** A judge following the README can hit three avoidable failures before seeing the app.

**Fix prompt:**

```text
Fix the Quick Start in README.md. Copy .env.example to the project root (not backend/) or explicitly say the app reads the root .env. Change the install command to pip install -e ".[dev]" for the testing path, or add a separate runtime-only command. Change the Python prerequisite to "Python 3.12.x (3.13+ is not supported by pyproject.toml)". Ensure the sequence works from a clean clone with no existing .env: create venv, install with dev extras, copy env example to root, start uvicorn, run pytest.
```

### B4 - Live PayPal and real AI remain unverified

**Status:** NOT VERIFIED (blocking for the claims, not necessarily for the code)
**Evidence:**

- No `.env` file exists in the repository or the audit copy; only `.env.example` with blank credentials.
- `/api/health` returned `paypal_configured: false`, `paypal_mode: "disabled"`, `ai_provider: "demo"`.
- Every payment test used `DEMO-ORDER-*` / `DEMO-CAP-*` IDs.
- No OpenAI/Anthropic call was made; the assistant returned the deterministic demo engine output.

**Impact:** The implementation looks correct statically, but the submission claims a real Sandbox integration and real AI. Those claims must be proven before recording the demo video or claiming completion. If judges only see demo mode, R2 is effectively demo-only and R1's "real Sandbox transaction" statement is unsupported.

**Fix prompt:**

```text
Add a pre-submission verification script or checklist section that requires real credentials: set PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, AI_PROVIDER, and the matching AI key in a local .env (never commit it), then create a Sandbox order, approve it with a Sandbox buyer, capture it, and confirm the record is mode="sandbox" with a real PayPal order/capture ID. Ask the assistant a question and confirm provider is not "demo" and mode is "live". Record the exact commands and outputs in a VERIFICATION.md file, redacting secrets. Do not mark the live checks complete until they have actually run.
```

---

## 6. Should-fix issues

### S1 - Assistant UI discards the grounded references and facts

**Status:** PARTIAL
**Evidence:** The backend returns `answer`, `facts`, `recommendations`, `references`, `confidence`, and `disclaimer` (verified in the `/api/assistant/chat` response). The UI stores only `res.answer`:

```tsx
// frontend/src/pages/Assistant.tsx:31
setMessages((prev) => [...prev, { role: "assistant", content: res.answer }]);
```

**Impact:** The feature that distinguishes this project - grounded answers with transaction references - is invisible to judges. The spec item for showing transaction references is not met in the UI even though the backend provides them.

**Fix prompt:**

```text
Update the assistant chat UI to render the full grounded response, not just answer. Extend the ChatMessage type to carry facts, recommendations, references, confidence, and disclaimer from ChatResponse. Render references as clickable links to /transactions/:id, show a compact confidence badge, and show the disclaimer. Preserve existing styling and keep the answer as the primary text. Add a frontend test or at least verify with the demo response that all sections render.
```

### S2 - Transaction detail status history is always empty

**Status:** PARTIAL
**Evidence:**

- `frontend/src/lib/types.ts:42` declares `events: TransactionEvent[]`.
- `frontend/src/pages/TransactionDetail.tsx:124` renders `tx.events?.map(...)`.
- `backend/app/schemas.py:74-92` `TransactionOut` has no `events` field, and no serializer adds one.

**Impact:** The "status history" section never shows anything, which looks like a broken feature during the demo.

**Fix prompt:**

```text
Add transaction status history end to end. Either derive an events array in the backend serializer from created_at, updated_at, completed_at, status, paypal_status, and failure_reason, or add a transaction_events table populated on create/capture/cancel/sync. Include it in TransactionOut as events: list[TransactionEvent]. Update frontend types to match non-optional data and render the existing TransactionDetail section. Add a backend test asserting events are returned for created and completed transactions.
```

### S3 - PayPal idempotency header is missing

**Status:** PARTIAL
**Evidence:**

- No `PayPal-Request-Id` header is sent anywhere (grep found only explanatory comments).
- `backend/app/services/paypal.py:324` creates an order without an idempotency key.
- `backend/app/services/paypal.py:331-348` handles `ORDER_ALREADY_CAPTURED` by re-fetching, and the local recapture path returns `already_captured: true` (verified).
- `backend/app/services/payments.py:146` implements local capture idempotency.

**Impact:** Capture retries are handled, but create-order retries (double click, network retry, proxy replay) can create duplicate PayPal orders. The docs/checklist describe idempotent behavior more broadly than the implementation supports.

**Fix prompt:**

```text
Add PayPal-Request-Id idempotency keys to PayPal create and capture requests. Generate a deterministic key per logical operation (for example a client-supplied request id or a stable hash of transaction_id plus amount/currency/description for create, and the transaction id for capture), pass it through PayPalClient._request as a header, and store/reuse it for retries. Do not send secrets in the key. Add tests asserting the header is present on create and capture and that a retried create with the same key reuses the same logical order where PayPal supports it.
```

### S4 - Docker volume hides application code on rebuilds

**Status:** PARTIAL
**Evidence:** `docker-compose.yml:32-33` mounts `paypilot-data:/app` over the entire application directory.

**Impact:** First run may work because Docker initializes an empty named volume from the image, but after a rebuild the volume can preserve old code and frontend assets, producing confusing stale behavior.

**Fix prompt:**

```text
Change docker-compose.yml to mount persistent data at a dedicated path (for example paypilot-data:/app/data) and set DATABASE_URL=sqlite:////app/data/paypilot.db. Ensure the directory exists and is writable by the non-root appuser in the Dockerfile. Verify that rebuilding the image updates app code while the SQLite file survives.
```

### S5 - Create-order response echoes unnormalised amount

**Status:** PARTIAL (minor correctness/transparency)
**Evidence:**

- `POST /api/payments/create-order` with `amount: "10.999"` returned 200 with `"amount": "10.999"`.
- The record stored `amount_minor: 1100` (11.00 USD), because `backend/app/money.py` rounds half-up to minor units.
- `backend/app/schemas.py:152-193` accepts the raw string and the router echoes `payload.amount` (`backend/app/routers/payments.py:74`).

**Impact:** The API response and the persisted record disagree for amounts with extra decimal places. In live mode the PayPal request is formatted from minor units, so PayPal would see 11.00 while the immediate create response shows 10.999. Judges using normal 2-decimal amounts will not hit this, but it is an avoidable inconsistency.

**Fix prompt:**

```text
Make create-order amount handling consistent. Either reject amounts with more decimal places than the currency allows (return 422 with a clear message), or normalize the amount through parse_amount_to_minor/format_amount and return the normalized value in CreateOrderResponse. Ensure the response amount always equals the stored amount and the value sent to PayPal. Add tests for 2-decimal, 3-decimal, and zero-decimal currencies.
```

### S6 - Working tree contains untracked test scripts and response dumps

**Status:** PARTIAL (submission hygiene)
**Evidence:** `git status --short` shows untracked `backend/assistant_response.json`, `backend/create_order_response.json`, `backend/check_routes.py`, and `backend/test_*.py` scripts, in addition to ignored DB files.

**Impact:** The repository is not clean, and a judge browsing the source may see ad-hoc scripts that look like part of the product. Some may contain response data.

**Fix prompt:**

```text
Clean the working tree before submission. Review each untracked backend/test_*.py, check_routes.py, and *_response.json file. Move genuinely useful checks into backend/tests/ as proper pytest tests, delete one-off dumps and generated response JSON, and add patterns for generated JSON dumps to .gitignore if needed. Do not commit secrets or database files. Finish with a clean git status.
```

### S7 - Several documentation claims are false or stale

**Status:** FAIL for accuracy
**Evidence:** See section 7. Most important: Docker success claims, "public source repository ready", and the video claim. The 233-test claim is accurate.

**Fix prompt:**

```text
Audit all submission docs for truthfulness. Correct SUBMISSION_CHECKLIST.md, README.md, TECHNICAL_REPORT.md, RESUME_DESCRIPTION.md, and DEMO_SCRIPT.md so no item is marked complete unless the linked artifact exists. Replace "Docker builds successfully" with the actual verified status until B1 is fixed. Replace the placeholder YouTube URL with the real URL or mark it pending. Align the Python version and test install instructions with pyproject.toml.
```

### S8 - No lint or CI gate

**Status:** NICE-TO-HAVE / PARTIAL
**Evidence:** `frontend/package.json` has `dev`, `build`, `typecheck`, `preview`; no `lint` script or ESLint config. No CI workflow exists.

**Fix prompt:**

```text
Add a minimal quality gate. Add an ESLint flat config and a lint script to frontend/package.json, and add a GitHub Actions workflow that runs Python 3.12 backend tests, frontend npm ci, npm run build, and npm run lint. Keep the workflow optional for local development but required for the public repository.
```

---

## 7. Documentation truthfulness matrix

| Claim | Location | Verdict |
|---|---|---|
| "233 tests pass" | `README.md:107`, `SUBMISSION_CHECKLIST.md:24`, `TECHNICAL_REPORT.md:87` | **TRUE** - verified 233 passed in 5.19s. |
| "233 passing tests, zero external dependencies" | `DEMO_SCRIPT.md:89` | **TRUE** - tests pass offline with mocked externals. |
| "docker compose up --build builds image successfully" | `SUBMISSION_CHECKLIST.md:47` | **FALSE** - build fails on missing `backend/README.md`; runtime lacks `gunicorn`. |
| "Container starts and serves on port 8000" | `SUBMISSION_CHECKLIST.md:48` | **FALSE** until B1 is fixed. |
| "Runs locally in 2 commands (`docker compose up` ...)" | `SUBMISSION_CHECKLIST.md:90` | **FALSE** for the Docker command; the uvicorn + npm path works. |
| "Complete setup instructions" | `SUBMISSION_CHECKLIST.md:14`, `README.md:119` | **PARTIAL** - extensive, but the Quick Start has the `cp` and dev-extra defects. |
| Python 3.12+ | `README.md:22` | **PARTIAL** - must be 3.12.x; 3.13/3.14 are rejected by `pyproject.toml`. |
| "Public source repository ready" | `README.md:117` | **FALSE** - no remote configured. |
| "Public source repository" pending | `SUBMISSION_CHECKLIST.md:12` | **TRUE/honest** - correctly marked pending. |
| "YouTube demo video <3 min" | `SUBMISSION_CHECKLIST.md:16` | **FALSE** - only a script exists; `RESUME_DESCRIPTION.md:45` has a placeholder URL. |
| "Real AI model / AI platform integration" | `SUBMISSION_CHECKLIST.md:8` | **PARTIAL** - real providers are implemented, but no live call was demonstrated. |
| "Creates & captures PayPal Sandbox payments end to end" | `SUBMISSION_CHECKLIST.md:81` | **NOT VERIFIED** - demo flow only in this audit. |
| "No secrets in repository" | `SUBMISSION_CHECKLIST.md:62` | **TRUE** - scan found placeholders only. |
| "Sandbox-only enforcement" | `SUBMISSION_CHECKLIST.md:65` | **TRUE** - config interlock enforces it. |
| "Ready for submission" | `SUBMISSION_CHECKLIST.md:165` | **FALSE** - see blocking issues. |

---

## 8. Additional verified strengths

- **Server-side trust boundary:** the browser never supplies amount/currency as authority; capture re-validates ownership, amount, and currency before persisting (`backend/app/services/payments.py`).
- **Token handling:** OAuth token is cached with an expiry margin and refreshed on 401 (`backend/app/services/paypal.py:120-176`).
- **Sandbox safety:** `PAYPAL_MODE=live` is blocked unless `ALLOW_LIVE_PAYMENTS=true`, and a sandbox mode requires a sandbox base URL (`backend/app/config.py`).
- **Demo labelling:** every seeded row is `is_demo_record=True` / `mode="demo"`; API responses carry explicit notices; UI has a mode banner.
- **Error handling:** structured error codes, validation messages, PayPal error mapping, request-size limit, rate limits, and security headers.
- **Tests:** broad coverage across money math, PayPal service behavior, payments, reports, dashboard, config, and assistant grounding.
- **License:** standard MIT license with a 2026 copyright holder.
- **No secret leakage:** no `.env` tracked; `.gitignore` covers `.env`, DB files, `node_modules`, `dist`, `.venv`, and caches.

---

## 9. Residual risks and notes

- **No authentication:** anyone who can reach a deployed instance can create/capture Sandbox orders and read all transactions. `README.md:134` discloses this. Acceptable for a local hackathon demo; not acceptable for a public deployment.
- **In-memory rate limiting:** limits reset on restart and are per-process; fine for a demo, not a distributed deployment.
- **SQLite:** appropriate for the demo; not a concurrency or durability story for production.
- **Mojibake in terminal output:** em dashes in some docs/API output appeared garbled under PowerShell 5.1. This is a console encoding display issue, not a functional failure; files are UTF-8.
- **Docker daemon unavailable:** the actual image build was not run. B1's build failure was reproduced by simulating the exact install step, and the missing `gunicorn` runtime is independently confirmed. Re-run `docker compose build` after the fix.
- **Live credentials absent:** do not record the "real Sandbox transaction" segment until a Sandbox buyer approval and capture have actually been performed.

---

## 10. Recommended order of work

1. Fix B1 (Docker) and verify `docker compose build`, `up`, health check.
2. Fix B3 (Quick Start) and verify from a clean clone on Python 3.12.
3. Fix S1 and S2 (assistant references, transaction events) because they are visible in the demo.
4. Fix S3 (idempotency) and S5 (amount consistency) before claiming payment robustness.
5. Set real PayPal Sandbox and AI credentials; run B4 verification; record the video.
6. Complete B2 submission assets: public repo, video, tools statement.
7. Clean S6, correct S7 docs, then re-run all verification commands.

---

## 11. Final status summary

| Item | Status |
|---|---|
| Local backend demo | **PASS** |
| Local frontend demo | **PASS** |
| Backend test suite | **PASS (233/233)** |
| Frontend production build | **PASS** |
| Demo honesty/labelling | **PASS** |
| Security/secrets | **PASS (no-auth caveat)** |
| Docker path | **FAIL** |
| Quick Start docs | **FAIL** |
| Public repo/video/tools statement | **FAIL** |
| Live PayPal Sandbox | **NOT VERIFIED** |
| Real AI provider | **NOT VERIFIED** |
| Submission readiness | **NOT READY** |

---

## 12. Fix pass (2026-11-04)

### Fixed items

| Item | Description | Verification |
|------|-------------|--------------|
| **B1 - Docker build** | Fixed Dockerfile to copy `backend/README.md` before `pip install`; switched from `gunicorn` to `uvicorn` (no extra dependency); fixed `docker-compose.yml` to mount named volume only at `/app/data` for SQLite persistence with `DATABASE_URL=sqlite:////app/data/paypilot.db` | Code changes verified; `docker compose config` validates; **NOT VERIFIED** - Docker daemon unavailable in audit environment |
| **B3 - Quick Start** | Fixed `README.md`: Python version corrected to "3.12.x (3.13+ not supported)"; `.env.example` copy path fixed to project root; install command changed to `pip install -e ".[dev]"` | **VERIFIED** - commands work from clean clone on Python 3.12 |
| **S3 - PayPal idempotency** | Added `PayPal-Request-Id` header to `create_order` and `capture_order`; generate stable UUID per payment request stored in new `paypal_request_id` column; reuse on retry; handle duplicate capture safely returning `already_captured: true`; added mocked tests | **VERIFIED** - 237 backend tests pass (includes 4 new idempotency tests) |
| **S1 - Assistant UI** | Extended `ChatMessage` type with `facts`, `recommendations`, `references`, `confidence`, `disclaimer`; render each as visually distinct section; transaction references as clickable links to `/transactions/:id`; show confidence badge and disclaimer | **VERIFIED** - frontend TypeScript build passes (`npm run build`) |
| **Test infrastructure** | Fixed test database schema sync: `dispose_engine()` returns engine; `conftest.py` drops and recreates tables on import to pick up model changes | **VERIFIED** - all 237 backend tests pass |

### Still NOT VERIFIED (require external credentials)

| Item | Reason |
|------|--------|
| **B4 - Live PayPal Sandbox** | No `PAYPAL_CLIENT_ID`/`PAYPAL_CLIENT_SECRET` configured; all tests run in demo mode with `DEMO-ORDER-*` IDs |
| **B4 - Real AI provider** | `AI_PROVIDER=demo`; no OpenAI/Anthropic API keys; assistant uses deterministic demo engine |
| **B2 - Submission assets** | No public git remote; YouTube video URL is placeholder; no AI_TOOLS_STATEMENT.md |
| **Docker runtime** | Docker daemon not available in audit environment; `docker compose build` / `up` / `curl /api/health` not executed |

### Remaining should-fix items (not addressed)

- **S2** - Transaction detail status history (events) still empty in backend serializer
- **S5** - Create-order response echoes unnormalized amount (minor)
- **S6** - Working tree contains untracked test scripts (`backend/test_*.py`, `backend/check_routes.py`, response JSON dumps)
- **S7** - Documentation claims in SUBMISSION_CHECKLIST.md, TECHNICAL_REPORT.md, RESUME_DESCRIPTION.md, DEMO_SCRIPT.md still reference false Docker/video status
- **S8** - No lint script or CI workflow

### Test results after fixes

- Backend: **237 tests passed** (was 233, +4 idempotency tests)
- Frontend: **TypeScript + Vite build PASS** (2197 modules, 645 kB JS bundle)
