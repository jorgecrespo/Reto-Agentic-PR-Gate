FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.7
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/src ./src
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
COPY config ./config
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app \
    && mkdir /data && chown app:app /data
ENV PYTHONPATH=/app/src UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/uv
USER app
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "pr_gate.main:app", "--host", "0.0.0.0", "--port", "8000"]
