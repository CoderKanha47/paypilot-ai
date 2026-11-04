# PayPilot AI — Multi-stage Dockerfile
# Builds frontend, installs backend deps, serves SPA from FastAPI

# ---------- Stage 1: Frontend build ----------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Backend runtime ----------
FROM python:3.12-slim AS runtime
WORKDIR /app

# System deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/pyproject.toml backend/uv.lock* backend/README.md ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir .

# Copy backend source
COPY backend/app ./app

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Non-root user
RUN useradd --no-create-home --uid 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app
USER appuser

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    SEED_DEMO_DATA=false

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health', timeout=3).raise_for_status()" || exit 1

EXPOSE 8000

# Run with uvicorn for production (gunicorn not required)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]