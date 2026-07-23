#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
printf '%s\n' "This removes containers and the SQLite Docker volume."
exec docker compose --project-directory "$ROOT" down --volumes --remove-orphans
