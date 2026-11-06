# ==============================================================================
# ActiveQueue Workspace Makefile
# ==============================================================================

.DEFAULT_GOAL := help

# Colors for terminal output
BLUE    := \033[36m
GREEN   := \033[32m
YELLOW  := \033[33m
RESET   := \033[0m

.PHONY: help install install-backend install-frontend \
        local dev dev-backend dev-frontend dev-web dev-emulators \
        storybook storybook-ios storybook-android \
        docker-up docker-down docker-build emulators emulators-stop \
        seed-db seed \
        check contracts test test-backend test-backend-fast test-emulator test-frontend \
        lint lint-backend lint-frontend \
        typecheck typecheck-backend typecheck-frontend \
        format format-backend \
        clean

## help: Display available Makefile targets
help:
	@echo ""
	@echo "$(BLUE)ActiveQueue Development Commands:$(RESET)"
	@echo ""
	@echo "  $(GREEN)install$(RESET)           Install all dependencies (backend + frontend)"
	@echo "  $(GREEN)install-backend$(RESET)   Install backend dependencies via uv"
	@echo "  $(GREEN)install-frontend$(RESET)  Install frontend dependencies via pnpm"
	@echo ""
	@echo "  $(GREEN)local$(RESET)             Start everything: emulators (Docker) + backend + frontend"
	@echo "  $(GREEN)dev$(RESET)               Start full stack without emulators (FastAPI + Expo)"
	@echo "  $(GREEN)dev-backend$(RESET)       Start FastAPI backend server on port 8080"
	@echo "  $(GREEN)dev-frontend$(RESET)      Start Expo frontend Metro server"
	@echo "  $(GREEN)dev-web$(RESET)           Start Expo frontend Web server"
	@echo ""
	@echo "  $(GREEN)storybook$(RESET)         Alias for storybook-ios"
	@echo "  $(GREEN)storybook-ios$(RESET)     Run on-device Storybook on iOS simulator"
	@echo "  $(GREEN)storybook-android$(RESET) Run on-device Storybook on Android emulator"
	@echo ""
	@echo "  $(GREEN)docker-up$(RESET)         Start local Docker services (Firebase emulators)"
	@echo "  $(GREEN)docker-down$(RESET)       Stop and remove all local Docker containers"
	@echo "  $(GREEN)docker-build$(RESET)      Rebuild Docker images for local services"
	@echo "  $(GREEN)emulators$(RESET)         Alias for docker-up"
	@echo "  $(GREEN)emulators-stop$(RESET)    Alias for docker-down"
	@echo "  $(GREEN)seed-db$(RESET)         Seed local Firestore and Auth emulators with mock test data"
	@echo "  $(GREEN)seed$(RESET)            Alias for seed-db"
	@echo ""
	@echo "  $(GREEN)check$(RESET)             Run every CI gate locally (lint, types, tests, coverage)"
	@echo "  $(GREEN)test$(RESET)              Run all unit tests (backend + frontend)"
	@echo "  $(GREEN)test-backend$(RESET)      Full pytest suite on test emulators + 95% coverage gate"
	@echo "  $(GREEN)test-backend-fast$(RESET) Unit + mocked integration tests only (no emulators)"
	@echo "  $(GREEN)test-emulator$(RESET)     Start test emulators (9190/9199) in the foreground"
	@echo "  $(GREEN)test-frontend$(RESET)     Run Jest test suite in frontend"
	@echo "  $(GREEN)contracts$(RESET)         Regenerate API contract files after an API change"
	@echo ""
	@echo "  $(GREEN)lint$(RESET)              Run linting & typechecking across full stack"
	@echo "  $(GREEN)lint-backend$(RESET)      Run ruff lint on backend"
	@echo "  $(GREEN)lint-frontend$(RESET)     Run eslint on frontend"
	@echo "  $(GREEN)typecheck$(RESET)         Run static type checks (mypy + tsc)"
	@echo "  $(GREEN)typecheck-backend$(RESET) Run mypy on backend"
	@echo "  $(GREEN)typecheck-frontend$(RESET)Run tsc on frontend"
	@echo ""
	@echo "  $(GREEN)format$(RESET)            Format backend code with ruff"
	@echo "  $(GREEN)clean$(RESET)             Clean temporary build cache directories"
	@echo ""

# ==============================================================================
# INSTALLATION & DEPENDENCIES
# ==============================================================================

## install: Install dependencies for both backend and frontend
install: install-backend install-frontend

## install-backend: Install Python backend dependencies using uv
install-backend:
	@echo "$(BLUE)Installing backend dependencies...$(RESET)"
	cd backend && uv sync

## install-frontend: Install Node frontend dependencies using pnpm
install-frontend:
	@echo "$(BLUE)Installing frontend dependencies...$(RESET)"
	cd frontend && pnpm install

# ==============================================================================
# DEVELOPMENT SERVERS
# ==============================================================================

## local: Start full local environment (Docker infra + FastAPI backend + Expo frontend)
local:
	@echo "$(BLUE)Starting full local environment...$(RESET)"
	@echo "$(BLUE)  → Docker: Firebase Auth (9099) + Firestore (9090) + Emulator UI (4000)$(RESET)"
	@echo "$(BLUE)  → Backend: FastAPI (8080)$(RESET)"
	@echo "$(BLUE)  → Frontend: Expo Metro$(RESET)"
	@docker compose up -d firebase-emulators
	@echo "$(YELLOW)Waiting for emulators to be ready...$(RESET)"
	@docker compose exec -T firebase-emulators sh -c 'until curl -sf http://localhost:4000 >/dev/null 2>&1; do sleep 2; done'
	@echo "$(GREEN)Emulators ready!$(RESET)"
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080) & \
	(cd frontend && pnpm start) & \
	wait

## dev: Run FastAPI backend and Expo frontend concurrently (no emulators)
dev:
	@echo "$(BLUE)Starting FastAPI backend (port 8080) & Expo frontend...$(RESET)"
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080) & \
	(cd frontend && pnpm start) & \
	wait

## dev-backend: Run FastAPI backend with Uvicorn auto-reload
dev-backend:
	@echo "$(BLUE)Starting FastAPI backend server on http://localhost:8080...$(RESET)"
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

## dev-frontend: Run Expo frontend Metro server
dev-frontend:
	@echo "$(BLUE)Starting Expo frontend Metro server...$(RESET)"
	cd frontend && pnpm start

## docker-up: Start local Docker services (Firebase emulators) in background
docker-up:
	@echo "$(BLUE)Starting local Docker services (Firebase Auth + Firestore emulators)...$(RESET)"
	docker compose up -d firebase-emulators
	@echo "$(GREEN)Emulator UI: http://localhost:4000$(RESET)"

## docker-down: Stop and remove all local Docker containers
docker-down:
	@echo "$(YELLOW)Stopping local Docker containers...$(RESET)"
	docker compose down
	@echo "$(GREEN)Local Docker services stopped.$(RESET)"

## docker-build: Rebuild Docker images for local services
docker-build:
	@echo "$(BLUE)Rebuilding local Docker images...$(RESET)"
	docker compose build --no-cache
	@echo "$(GREEN)Docker images rebuilt.$(RESET)"

## emulators: Start Firebase emulators in Docker (alias for docker-up)
emulators: docker-up

## emulators-stop: Stop Firebase emulators (alias for docker-down)
emulators-stop: docker-down

## dev-emulators: Alias for local (backwards compat)
dev-emulators: local

## dev-web: Run Expo frontend Web server
dev-web:
	@echo "$(BLUE)Starting Expo Web frontend server...$(RESET)"
	cd frontend && pnpm web

## storybook: Alias for storybook-ios
storybook: storybook-ios

## storybook-ios: Run on-device Storybook on iOS simulator
storybook-ios:
	@echo "$(BLUE)Starting Storybook on iOS simulator...$(RESET)"
	cd frontend && pnpm storybook:ios

## storybook-android: Run on-device Storybook on Android emulator
storybook-android:
	@echo "$(BLUE)Starting Storybook on Android emulator...$(RESET)"
	cd frontend && pnpm storybook:android

# ==============================================================================
# DATABASE SEEDING
# ==============================================================================

## seed-db: Seed local Firestore and Auth emulators with test data
seed-db:
	@echo "$(BLUE)Seeding local database with test data...$(RESET)"
	cd backend && uv run python -m app.cli.seed

## seed: Alias for seed-db
seed: seed-db

# ==============================================================================
# TESTING
# ==============================================================================

## test: Run tests for both backend and frontend
test: test-backend test-frontend

## check: The same gates CI enforces (see docs/testing.md). Run before pushing.
check:
	@echo "$(BLUE)[1/6] Backend lint & format$(RESET)"
	cd backend && uv run ruff check app tests && uv run ruff format --check app tests
	@echo "$(BLUE)[2/6] Backend types (mypy --strict)$(RESET)"
	cd backend && uv run mypy --strict app
	@echo "$(BLUE)[3/6] Backend tests on test emulators + coverage gate$(RESET)"
	$(MAKE) test-backend
	@echo "$(BLUE)[4/6] Frontend lint & types$(RESET)"
	cd frontend && pnpm lint && pnpm typecheck
	@echo "$(BLUE)[5/6] Frontend tests + coverage gate + untested-file check$(RESET)"
	cd frontend && pnpm test:coverage && node scripts/check-untested-files.js coverage/coverage-final.json
	@echo "$(BLUE)[6/6] Workflow lint (actionlint, via Docker)$(RESET)"
	docker run --rm -v "$(CURDIR):/repo" -w /repo rhysd/actionlint:1.7.11 -color
	@echo "$(GREEN)All CI gates passed locally.$(RESET)"

# Test emulators use firebase.test.json (Firestore 9190, Auth 9199) so a test run never
# wipes the dev emulators started by `make local`. Requires Java 21+.
FIREBASE_TOOLS  := npx -y firebase-tools@15.33.0
TEST_EMULATORS  := --config firebase.test.json --project demo-activequeue-local --only auth,firestore

## test-backend: Full backend suite (unit + mocked + emulator tiers) with the coverage gate
test-backend:
	@echo "$(BLUE)Running backend pytest suite against the test emulators...$(RESET)"
	$(FIREBASE_TOOLS) emulators:exec $(TEST_EMULATORS) \
		"cd backend && REQUIRE_EMULATOR=1 uv run pytest --cov"

## test-backend-fast: Unit + mocked integration tiers only (no emulators, no coverage gate)
test-backend-fast:
	cd backend && uv run pytest tests/unit tests/integration tests/contract

## test-emulator: Run the test emulators in the foreground (for iterating on tests/emulator)
test-emulator:
	$(FIREBASE_TOOLS) emulators:start $(TEST_EMULATORS)

## contracts: Regenerate contracts/openapi.json after an intentional API change
contracts:
	@echo "$(BLUE)Regenerating API contract files...$(RESET)"
	cd backend && UPDATE_CONTRACTS=1 uv run pytest -p no:randomly tests/contract/test_openapi_snapshot.py

## test-frontend: Run Jest test suite on frontend (random order, coverage gate)
test-frontend:
	@echo "$(BLUE)Running frontend Jest test suite...$(RESET)"
	cd frontend && pnpm test:coverage

# ==============================================================================
# LINTING & TYPE CHECKING
# ==============================================================================

## lint: Run linting and typechecking for both backend and frontend
lint: lint-backend lint-frontend typecheck

## lint-backend: Run ruff linter on backend
lint-backend:
	@echo "$(BLUE)Linting backend with ruff...$(RESET)"
	cd backend && uv run ruff check app tests

## lint-frontend: Run eslint on frontend
lint-frontend:
	@echo "$(BLUE)Linting frontend with eslint...$(RESET)"
	cd frontend && pnpm lint

## typecheck: Run typechecking for backend (mypy) and frontend (tsc)
typecheck: typecheck-backend typecheck-frontend

## typecheck-backend: Run mypy typechecker on backend
typecheck-backend:
	@echo "$(BLUE)Typechecking backend with mypy...$(RESET)"
	cd backend && uv run mypy --strict app

## typecheck-frontend: Run TypeScript compiler on frontend
typecheck-frontend:
	@echo "$(BLUE)Typechecking frontend with tsc...$(RESET)"
	cd frontend && pnpm typecheck

## format: Format backend code using ruff
format: format-backend

## format-backend: Format backend Python files using ruff
format-backend:
	@echo "$(BLUE)Formatting backend with ruff...$(RESET)"
	cd backend && uv run ruff format .

# ==============================================================================
# CLEANUP
# ==============================================================================

## clean: Remove caches and build artifacts
clean:
	@echo "$(YELLOW)Cleaning caches and temporary build files...$(RESET)"
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache backend/.coverage
	rm -rf frontend/node_modules/.cache
