#!/usr/bin/env bash
# Run every test suite: pytest (backend), Vitest (frontend unit), Playwright (end-to-end).
# Starts Postgres via Docker Compose unless SKIP_DB=1 (CI provides a service container).
# Playwright starts/stops the backend (gunicorn) and frontend (vite preview) itself.
#
# Env: PYTHON (default backend/.venv/bin/python), SKIP_DB, SKIP_E2E,
#      DB_HOST/DB_PORT/DB_USER/DB_PASSWORD (default localhost/5432/qi/qi)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/backend/.venv/bin/python}"
DB_HOST="${DB_HOST:-localhost}" DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-qi}" DB_PASSWORD="${DB_PASSWORD:-qi}"
DB_BASE="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}"
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-$DB_BASE/qi_rhythm_test}"
export E2E_DATABASE_URL="${E2E_DATABASE_URL:-$DB_BASE/qi_rhythm_e2e}"
export E2E_PYTHON="$PYTHON"

STARTED_DB=0
declare -A RESULT

cleanup() {
  if [[ "$STARTED_DB" == 1 ]]; then
    echo "==> Stopping Postgres"
    (cd "$ROOT" && docker compose stop db >/dev/null)
  fi
}
trap cleanup EXIT

if [[ "${SKIP_DB:-0}" != 1 ]]; then
  if ! (cd "$ROOT" && docker compose ps --status running db 2>/dev/null | grep -q db); then
    echo "==> Starting Postgres"
    (cd "$ROOT" && docker compose up -d db) || exit 1
    STARTED_DB=1
  fi
  for _ in $(seq 1 60); do
    (cd "$ROOT" && docker compose exec -T db pg_isready -U "$DB_USER" >/dev/null 2>&1) && break
    sleep 1
  done
fi

echo "==> Ensuring test databases exist"
"$PYTHON" - <<PY || exit 1
import psycopg
with psycopg.connect("postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/postgres", autocommit=True) as c:
    for name in ("qi_rhythm_test", "qi_rhythm_e2e"):
        if not c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            c.execute(f'CREATE DATABASE "{name}"')
PY

run() {
  local name="$1"; shift
  echo; echo "==> $name"
  if "$@"; then RESULT[$name]=passed; else RESULT[$name]=FAILED; fi
}

run "backend pytest" bash -c "cd '$ROOT/backend' && '$PYTHON' -m pytest -q"
run "frontend vitest" bash -c "cd '$ROOT/frontend' && npm test --silent"
if [[ "${SKIP_E2E:-0}" != 1 ]]; then
  run "playwright e2e" bash -c "cd '$ROOT/frontend' && npx playwright test"
fi

echo; echo "==> Summary"
status=0
for name in "backend pytest" "frontend vitest" "playwright e2e"; do
  [[ -n "${RESULT[$name]:-}" ]] || continue
  printf '  %-18s %s\n' "$name" "${RESULT[$name]}"
  [[ "${RESULT[$name]}" == passed ]] || status=1
done
[[ -d "$ROOT/frontend/playwright-report" ]] && echo "  Playwright report: frontend/playwright-report/index.html"
exit $status
