#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec uv run --project "$ROOT/backend" alembic -c "$ROOT/backend/alembic.ini" upgrade head
