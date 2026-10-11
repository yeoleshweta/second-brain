FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY config ./config

RUN mkdir -p /data \
    /vault/00-Inbox/Daily \
    /vault/00-Inbox/Unsorted \
    /vault/01-Knowledge/Notes \
    /vault/02-Health/Logs \
    /vault/03-Finance/Logs \
    /vault/04-People \
    /vault/05-Calendar \
    /vault/99-System/Templates \
    /vault/99-System/Logs

ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
ENV ENVIRONMENT=production
ENV DATABASE_URL=sqlite:////data/secondbrain.db
ENV DATA_DIR=/data
ENV OBSIDIAN_VAULT_PATH=/vault

EXPOSE 8000

CMD ["python", "-m", "src.api.main"]
