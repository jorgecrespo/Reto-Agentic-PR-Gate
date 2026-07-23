FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.4.2 ruff==0.15.22
RUN groupadd --gid 10001 runner && useradd --uid 10001 --gid runner --create-home runner
USER runner
WORKDIR /workspace
