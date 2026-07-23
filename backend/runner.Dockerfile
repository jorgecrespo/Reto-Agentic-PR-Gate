FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.4.2 ruff==0.15.22
USER nobody:nogroup
WORKDIR /workspace
