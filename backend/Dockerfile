FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY src ./src
ENV ENVIRONMENT=production
EXPOSE 8000
CMD ["uv", "run", "python", "-m", "src.api.main"]
