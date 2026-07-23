#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
run_pytest() {
  scenario=$1
  expected=$2
  set +e
  (
    cd "$ROOT/examples/demo_ecommerce/scenarios/$scenario"
    uv run --project "$ROOT/backend" python -m pytest -q
  )
  actual=$?
  set -e
  if [ "$actual" -ne "$expected" ]; then
    printf '%s\n' "Scenario $scenario returned $actual; expected $expected." >&2
    exit 1
  fi
}

printf '%s\n' "Defective baseline: regression test must fail functionally."
run_pytest defective 1
printf '%s\n' "Candidate correction: regression and suite must pass."
run_pytest candidate 0
printf '%s\n' "Safe change: suite must pass."
run_pytest safe 0
printf '%s\n' "Inconclusive fixture: mandatory sandbox validation is unavailable; expected gate status INCONCLUSIVE."
printf '%s\n' "Local demo completed. No GitHub API or LLM call was made."
