# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ETF Tracker is a small full-stack app for tracking a personal portfolio of **JSE-listed
ETFs** (Satrix / Sygnia funds). It consolidates the underlying equity holdings across the
ETFs you own, rolls them up into a single "look-through" view, and tracks live prices and
P&L in ZAR.

- **Backend**: FastAPI (Python), single module `server/main.py`, port **8002**.
- **Frontend**: SvelteKit + Svelte 5 (runes), static adapter, Vite dev server on port **5175**.
- **Data**: JSON files — there is **no database engine**.

## Common commands

All workflows go through the `Makefile` (run `make help` for the full list). The backend
expects a virtualenv at `.venv/`.

```sh
make install          # create .venv, pip install, npm install in frontend/
make dev              # run backend (8002) + frontend (5175) concurrently
make dev-backend      # uvicorn server.main:app --reload --port 8002
make dev-frontend     # vite dev (proxies /api -> 127.0.0.1:8002)
make build            # build frontend into frontend/dist/
make run              # production: backend serves the built frontend
make start / stop     # start/stop both services as background daemons (PID files)
make status           # check daemon status
make test             # backend pytest + frontend tests
make clean            # remove build artifacts and __pycache__
```

### Testing

```sh
make test-backend                          # unit tests (no running server needed)
.venv/bin/pytest tests/test_api.py -v      # same, direct invocation
.venv/bin/pytest tests/test_api.py -k health -v      # single test (tests are in classes; use -k)
make test-smoke                            # smoke tests against a LIVE server on :8002
```

- `tests/test_api.py` uses FastAPI's `TestClient` and patches module-level paths
  (`server.main._HOLDINGS_DB_PATH`, `_PORTFOLIO_PATH`, `_PRICE_CACHE_PATH`) onto
  `tmp_path` fixtures — it never touches real data or the network. yfinance is mocked.
- `tests/test_smoke.py` requires a running server (start it with `make start` first).
- `requirements-dev.txt` (pytest, httpx) is installed automatically by `make test-backend`.

### Known Makefile/script gaps

- `make lint-frontend` and `make test-frontend` call `npm run lint` / `npm run test`,
  but the frontend `package.json` defines **neither** script. The real type/lint check is
  `npm run check` (svelte-check); `test-frontend` has a `|| echo` fallback so it won't fail
  the build. Use `cd frontend && npm run check` to validate the frontend.
- `make lint-backend` only runs `py_compile` on `server/main.py` (a syntax check, not a
  real linter).

## Architecture

### Backend (`server/main.py`)

A single FastAPI module. Key design points:

- **Data is read from JSON, cached in-process.** `_load_holdings_db()` reads
  `data/etf_holdings_db.json` once into `_holdings_cache`; `POST /api/refresh` (and
  `_invalidate_cache()`) clears it so the next request re-reads the file.
- **Metadata keys are prefixed with `_`** (e.g. `_updated`, `_source`, `_last_refreshed`,
  `_page_hash`). `get_all_etf_codes()` filters out any top-level key starting with `_`, so
  ETF tickers and metadata coexist in the same JSON object. Per-ETF metadata uses the same
  convention.
- **Prices** come from `~/.tradingagents/etf_prices_cache.json` (outside the repo). The
  server is a **reader with fallback**: fresh cache (<1h) → try yfinance with an 8s hard
  timeout → stale cache (<24h, returned with `"stale": true`) → `None`. yfinance is called
  in a thread pool so a slow network can never hang a request beyond the timeout.
- **Currency / cents convention**: JSE tickers are queried from yfinance as `TICKER.JO`
  and their prices come back in **cents**. The cache always stores cents for `.JO` tickers;
  prices are divided by 100 (`p / 100.0`) only at display time. Currency is `ZAR` for `.JO`,
  `USD` otherwise.
- **Portfolio** lives in `~/.tradingagents/etf_portfolio.json` (also outside the repo).
  Adding a position that already exists averages the cost basis. `GET /api/portfolio`
  computes value/cost/P&L/weights; `GET /api/portfolio/rollup` does the **look-through**:
  for each position it weights every underlying holding by `(holding weight) × (ETF weight
  in portfolio)` and aggregates duplicate tickers across ETFs into consolidated holdings +
  sector allocation.
- **SPA serving**: if `frontend/dist/` exists, the app mounts `/_app` static assets and a
  catch-all route serves `index.html` for any non-`/api/` path. In dev this branch is
  inactive and the Vite proxy forwards `/api` to the backend instead.

API surface (all under `/api`): `health`, `etf` (list), `etf/{ticker}`,
`etf/{ticker}/raw`, `etf/status/meta`, `status/scrape`, `refresh` (POST),
`portfolio`, `portfolio/positions` (POST / DELETE), `portfolio/rollup`.

### Frontend (`frontend/`)

- SvelteKit with `@sveltejs/adapter-static` (output dir `dist/`, SPA `fallback: index.html`).
- **The real app is `src/routes/+page.svelte`** — a single tabbed page (Portfolio / ETFs /
  Consolidated / Status) that imports components from `src/lib/`. Note: `src/App.svelte` and
  `src/main.js` are leftover **stubs** and are not the entry point.
- Uses **Svelte 5 runes** (`$state`, etc.). New reactive code should use runes, not the
  Svelte 4 `let`-reactivity / stores style.
- `src/lib/api.js` is the single API client; `BASE = ''` means all calls are same-origin and
  rely on the Vite dev proxy (dev) or the FastAPI SPA host (prod). Add new endpoints here.
- `src/lib/utils.js` holds shared formatters (`formatZAR`, `formatPct`) and theme helpers.

### Data refresh workflows (`scripts/`)

Holdings and prices are refreshed by **separate out-of-band processes**, never by the server
during a request:

- **`refresh_holdings.py`** — maintenance helper for `data/etf_holdings_db.json`. Holdings
  scraping is **agent-driven**: an agent ("Hermes") uses `web_extract` to pull holdings from
  JS-rendered fund fact-sheet pages, then calls `python scripts/refresh_holdings.py --update
  TICKER '<json>'` to write them. `--status` shows DB freshness, `--check` lists ETFs older
  than 90 days. The canonical list of tracked ETFs + their TERs and source URLs lives in the
  `ETF_SOURCES` dict in this file.
- **`refresh_prices.py`** — writes the price cache (`~/.tradingagents/etf_prices_cache.json`).
  Intended for a **cron job**, not the server. Falls back through JSE MarketWatch → AVMF API
  → yfinance → existing stale cache, per ticker.
- **`scrape_status.py`** — shared helper imported by both the backend (`/api/status/scrape`)
  and the refresh scripts. Reads/writes `data/scrape_status.json` to track current and
  historical scrape runs (see the schema docstring at the top of the file).

When adding or removing a tracked ETF, update the ticker tables in **all three** of
`refresh_holdings.py` (`ETF_SOURCES`), `refresh_prices.py` (`TICKERS`), and the
`data/etf_holdings_db.json` `_scrape_urls` block to keep them in sync.

## Conventions & gotchas

- **State that persists between sessions lives outside the repo** in `~/.tradingagents/`
  (portfolio + price cache). Only `data/etf_holdings_db.json` (holdings) is version-controlled.
  `data/raw/` (raw scraped source) is gitignored and regenerable.
- ETF tickers are uppercased everywhere; `get_price` appends `.JO` to bare tickers.
- The frontend and backend ports are pinned (8002 / 5175) across the Makefile, Vite proxy,
  and the backend CORS allow-list — change all of them together.
