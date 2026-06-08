# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps needed to compile some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN pip install uv

# Copy only dependency files first (layer cache)
COPY backend/pyproject.toml backend/uv.lock ./

# Install all deps into /app/.venv
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY backend/src ./src
COPY backend/config ./config

# Persistent data directories (mount these as Railway volumes)
RUN mkdir -p /data /vault/00-Inbox /vault/01-Knowledge /vault/02-Health \
              /vault/03-Finance /vault/04-People /vault/05-Calendar

# Activate venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Cloud defaults — override all of these via Railway env vars
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV ENVIRONMENT=production
ENV DATABASE_URL=sqlite:////data/secondbrain.db
ENV DATA_DIR=/data
# Obsidian: use direct filesystem writes in cloud (no REST API plugin needed)
ENV OBSIDIAN_VAULT_PATH=/vault

EXPOSE 8000

CMD ["/app/.venv/bin/python", "-m", "src.api.main"]
