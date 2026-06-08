FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY backend/src ./src
COPY backend/config ./config

# Create persistent data directories (Railway mounts volumes over these)
RUN mkdir -p /data \
    /vault/00-Inbox/Daily \
    /vault/01-Knowledge \
    /vault/02-Health \
    /vault/03-Finance/Weekly \
    /vault/04-People \
    /vault/05-Calendar

ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Cloud defaults — all overridden by Railway environment variables
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV ENVIRONMENT=production
ENV DATABASE_URL=sqlite:////data/secondbrain.db
ENV DATA_DIR=/data
ENV OBSIDIAN_VAULT_PATH=/vault

EXPOSE 8000

CMD ["python", "-m", "src.api.main"]
