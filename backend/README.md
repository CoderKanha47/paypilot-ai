# PayPilot AI — Backend

FastAPI service that powers the PayPilot AI dashboard: PayPal Sandbox order
creation/capture, SQLite persistence, analytics, reports and the grounded AI
assistant.

See the root `README.md` for full setup instructions.

```bash
cd backend
uv sync --python 3.12 --extra dev
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
```
