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
        dev-backend dev-frontend dev-web \
        test test-backend test-frontend \
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
	@echo "  $(GREEN)dev-backend$(RESET)       Start FastAPI backend server on port 8080"
	@echo "  $(GREEN)dev-frontend$(RESET)      Start Expo frontend Metro server"
	@echo "  $(GREEN)dev-web$(RESET)           Start Expo frontend Web server"
	@echo ""
	@echo "  $(GREEN)test$(RESET)              Run all unit tests (backend + frontend)"
	@echo "  $(GREEN)test-backend$(RESET)      Run pytest suite with coverage in backend"
	@echo "  $(GREEN)test-frontend$(RESET)     Run Jest test suite in frontend"
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

## dev-backend: Run FastAPI backend with Uvicorn auto-reload
dev-backend:
	@echo "$(BLUE)Starting FastAPI backend server on http://localhost:8080...$(RESET)"
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

## dev-frontend: Run Expo frontend Metro server
dev-frontend:
	@echo "$(BLUE)Starting Expo frontend server...$(RESET)"
	cd frontend && pnpm start

## dev-web: Run Expo frontend Web server
dev-web:
	@echo "$(BLUE)Starting Expo Web frontend server...$(RESET)"
	cd frontend && pnpm web

# ==============================================================================
# TESTING
# ==============================================================================

## test: Run tests for both backend and frontend
test: test-backend test-frontend

## test-backend: Run pytest suite on backend with coverage report
test-backend:
	@echo "$(BLUE)Running backend pytest test suite...$(RESET)"
	cd backend && uv run pytest

## test-frontend: Run Jest test suite on frontend
test-frontend:
	@echo "$(BLUE)Running frontend Jest test suite...$(RESET)"
	cd frontend && pnpm test

# ==============================================================================
# LINTING & TYPE CHECKING
# ==============================================================================

## lint: Run linting and typechecking for both backend and frontend
lint: lint-backend lint-frontend typecheck

## lint-backend: Run ruff linter on backend
lint-backend:
	@echo "$(BLUE)Linting backend with ruff...$(RESET)"
	cd backend && uv run ruff check .

## lint-frontend: Run eslint on frontend
lint-frontend:
	@echo "$(BLUE)Linting frontend with eslint...$(RESET)"
	cd frontend && pnpm lint

## typecheck: Run typechecking for backend (mypy) and frontend (tsc)
typecheck: typecheck-backend typecheck-frontend

## typecheck-backend: Run mypy typechecker on backend
typecheck-backend:
	@echo "$(BLUE)Typechecking backend with mypy...$(RESET)"
	cd backend && uv run mypy app

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
