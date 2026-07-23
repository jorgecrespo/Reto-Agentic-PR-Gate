FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.7
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/src ./src
COPY config ./config
ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "pr_gate.main:app", "--host", "0.0.0.0", "--port", "8000"]
