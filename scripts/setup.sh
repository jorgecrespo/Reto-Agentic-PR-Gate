#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' "uv is required: https://docs.astral.sh/uv/"
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  printf '%s\n' "npm (Node 22) is required."
  exit 1
fi

uv sync --project "$ROOT/backend" --all-groups --frozen
npm --prefix "$ROOT/frontend" ci
printf '%s\n' "Dependencies installed. Copy .env.example to .env before real GitHub/LLM analysis."
