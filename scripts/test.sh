#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

uv run --project "$ROOT/backend" ruff format --check "$ROOT/backend"
uv run --project "$ROOT/backend" ruff check "$ROOT/backend"
uv run --project "$ROOT/backend" mypy "$ROOT/backend/src"
uv run --project "$ROOT/backend" pytest "$ROOT/backend/tests"
npm --prefix "$ROOT/frontend" run lint
npm --prefix "$ROOT/frontend" run typecheck
npm --prefix "$ROOT/frontend" run test -- --run
npm --prefix "$ROOT/frontend" run build
