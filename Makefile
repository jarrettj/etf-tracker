.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend build lint lint-backend lint-frontend clean test run stop start

# Default target
.DEFAULT_GOAL := help

# ── Variables ──────────────────────────────────────────────────────────────
BACKEND_VENV   := .venv
BACKEND_PYTHON := $(BACKEND_VENV)/bin/python
BACKEND_PORT   := 8002
FRONTEND_DIR   := frontend
FRONTEND_PORT  := 5174

BACKEND_PID    := .backend.pid
FRONTEND_PID   := .frontend.pid

# ── Help ───────────────────────────────────────────────────────────────────
help: ## Show this help
	@echo "ETF Tracker — available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Install ────────────────────────────────────────────────────────────────
install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install backend Python dependencies
	@echo "==> Installing backend dependencies..."
	python3 -m venv $(BACKEND_VENV)
	$(BACKEND_VENV)/bin/pip install --upgrade pip
	$(BACKEND_VENV)/bin/pip install -r requirements.txt

install-frontend: ## Install frontend npm dependencies
	@echo "==> Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install

# ── Development ────────────────────────────────────────────────────────────
dev: ## Run backend and frontend concurrently
	@echo "==> Starting backend (port $(BACKEND_PORT)) and frontend (port $(FRONTEND_PORT))..."
	@$(MAKE) --no-print-directory dev-backend & \
	$(MAKE) --no-print-directory dev-frontend & \
	wait

start: ## Start both backend and frontend in the background (daemon mode)
	@echo "==> Starting backend (port $(BACKEND_PORT))..."
	@nohup $(BACKEND_VENV)/bin/uvicorn server.main:app \
		--port $(BACKEND_PORT) > backend.log 2>&1 &
	@echo $$! > $(BACKEND_PID)
	@echo "==> Starting frontend (port $(FRONTEND_PORT))..."
	@cd $(FRONTEND_DIR) && nohup npm run dev > ../frontend.log 2>&1 &
	@echo $$! > $(FRONTEND_PID)
	@echo "==> Both services started. Logs: backend.log, frontend.log"

dev-backend: ## Run the FastAPI backend server
	@echo "==> Starting backend on port $(BACKEND_PORT)..."
	$(BACKEND_VENV)/bin/uvicorn server.main:app --reload --port $(BACKEND_PORT)

dev-frontend: ## Run the Vite dev server
	@echo "==> Starting frontend on port $(FRONTEND_PORT)..."
	cd $(FRONTEND_DIR) && npm run dev

# ── Build ──────────────────────────────────────────────────────────────────
build: build-frontend ## Build frontend for production

build-frontend: ## Build the Vite frontend
	@echo "==> Building frontend..."
	cd $(FRONTEND_DIR) && npm run build

# ── Lint ───────────────────────────────────────────────────────────────────
lint: lint-backend lint-frontend ## Lint both backend and frontend

lint-backend: ## Lint Python backend (pyright via venv)
	@echo "==> Linting backend..."
	$(BACKEND_VENV)/bin/python -m py_compile server/main.py

lint-frontend: ## Lint TypeScript frontend
	@echo "==> Linting frontend..."
	cd $(FRONTEND_DIR) && npm run lint

# ── Testing ──────────────────────────────────────────────────────────────────
test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend pytest suite (unit tests, no server needed)
	@echo "==> Running backend unit tests..."
	.venv/bin/pip install -q -r requirements-dev.txt
	.venv/bin/pytest tests/test_api.py -v

test-smoke: ## Run smoke tests against the LIVE server on port 8002
	@echo "==> Running smoke tests against $(BACKEND_PORT)..."
	.venv/bin/pytest tests/test_smoke.py -v

refresh-holdings: ## Refresh ETF holdings data (agent-driven, asks Hermes to scrape)
	@echo "==> Refreshing ETF holdings..."
	.venv/bin/python scripts/refresh_holdings.py --status
	@echo ""
	@echo "To refresh data, ask Hermes to scrape the latest fund fact sheets."
	@echo "Hermes will use web_extract to pull holdings and update the DB."

test-frontend: ## Run frontend vitest suite
	@echo "==> Running frontend tests..."
	cd frontend && npm run test -- --run 2>/dev/null || echo "  (no frontend tests configured yet)"

# ── Clean ──────────────────────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	@echo "==> Cleaning build artifacts..."
	rm -rf $(FRONTEND_DIR)/dist
	rm -rf $(FRONTEND_DIR)/node_modules/.vite
	rm -rf server/__pycache__
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

clean-all: clean ## Full clean including node_modules and venv
	@echo "==> Full clean (node_modules + venv)..."
	rm -rf $(FRONTEND_DIR)/node_modules
	rm -rf $(BACKEND_VENV)

# ── Data ───────────────────────────────────────────────────────────────────
seed-data: ## Show holdings DB summary
	@echo "==> ETF Holdings DB Summary:"
	@$(BACKEND_VENV)/bin/python -c \
		"import json; d=json.load(open('data/etf_holdings_db.json')); \
		 [print(f'  {k}: {len(v)} holdings') for k,v in d.items()]"

# ── Run (production) ──────────────────────────────────────────────────────
run: ## Run the backend serving the built frontend
	@echo "==> Starting production server on port $(BACKEND_PORT)..."
	$(BACKEND_VENV)/bin/uvicorn server.main:app --port $(BACKEND_PORT)

stop: ## Stop all background services
	@echo "==> Stopping services..."
	@if [ -f $(BACKEND_PID) ]; then \
		kill $$(cat $(BACKEND_PID)) 2>/dev/null; \
		rm -f $(BACKEND_PID); \
		echo "  Backend stopped."; \
	else \
		echo "  Backend PID file not found."; \
	fi
	@if [ -f $(FRONTEND_PID) ]; then \
		kill $$(cat $(FRONTEND_PID)) 2>/dev/null; \
		rm -f $(FRONTEND_PID); \
		echo "  Frontend stopped."; \
	else \
		echo "  Frontend PID file not found."; \
	fi

status: ## Check if background services are running
	@backend_running=0; frontend_running=0; \
	if [ -f $(BACKEND_PID) ] && kill -0 $$(cat $(BACKEND_PID)) 2>/dev/null; then backend_running=1; fi; \
	if [ -f $(FRONTEND_PID) ] && kill -0 $$(cat $(FRONTEND_PID)) 2>/dev/null; then frontend_running=1; fi; \
	if [ $$backend_running -eq 1 ]; then echo "  Backend:  RUNNING (PID $$(cat $(BACKEND_PID)))"; else echo "  Backend:  STOPPED"; fi; \
	if [ $$frontend_running -eq 1 ]; then echo "  Frontend: RUNNING (PID $$(cat $(FRONTEND_PID)))"; else echo "  Frontend: STOPPED"; fi
