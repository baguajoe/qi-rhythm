.PHONY: test-all test-backend test-frontend test-e2e lint db-up db-down

test-all:            ## Postgres + pytest + Vitest + Playwright, then shut everything down
	./scripts/test-all.sh

test-backend:
	cd backend && .venv/bin/python -m pytest -q

test-frontend:
	cd frontend && npm test

test-e2e:            ## needs Postgres running (make db-up)
	cd frontend && npx playwright test

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/black --check .
	cd frontend && npm run lint && npx prettier --check src e2e

db-up:
	docker compose up -d db

db-down:
	docker compose stop db
