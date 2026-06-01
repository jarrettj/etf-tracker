"""ETF Tracker — FastAPI server."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import json, os, hashlib
from datetime import datetime, timezone

app = FastAPI(title="ETF Tracker", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
_RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
_HOLDINGS_DB_PATH = Path(__file__).parent.parent / "data" / "etf_holdings_db.json"
_holdings_cache: dict | None = None

if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")


def _load_holdings_db() -> dict:
    global _holdings_cache
    if _holdings_cache is None:
        with open(_HOLDINGS_DB_PATH, encoding="utf-8") as f:
            _holdings_cache = json.load(f)
    return _holdings_cache


def _invalidate_cache():
    global _holdings_cache
    _holdings_cache = None


def get_etf_info(ticker: str) -> dict | None:
    db = _load_holdings_db()
    return db.get(ticker.upper())


def get_etf_holdings(ticker: str) -> list:
    info = get_etf_info(ticker)
    if info:
        return info.get("holdings", [])
    return []


def get_all_etf_codes() -> list[str]:
    db = _load_holdings_db()
    return [k for k in db.keys() if not k.startswith("_")]


def get_db_meta() -> dict:
    db = _load_holdings_db()
    codes = get_all_etf_codes()
    etfs = []
    for code in codes:
        info = get_etf_info(code)
        if info:
            etfs.append({
                "ticker": code,
                "name": info.get("name"),
                "last_refreshed": info.get("_last_refreshed"),
                "page_hash": info.get("_page_hash"),
                "holding_count": len(info.get("holdings", [])),
            })
    return {
        "etf_count": len(codes),
        "updated": db.get("_updated"),
        "source": db.get("_source"),
        "raw_dir": db.get("_raw_dir"),
        "etfs": etfs,
    }


_PORTFOLIO_PATH = Path.home() / ".tradingagents" / "etf_portfolio.json"


def _load_portfolio() -> dict:
    if not _PORTFOLIO_PATH.exists():
        return {"positions": [], "updated_at": None}
    try:
        return json.loads(_PORTFOLIO_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"positions": [], "updated_at": None}


def _save_portfolio(data: dict) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PORTFOLIO_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


_PRICE_CACHE_PATH = Path.home() / ".tradingagents" / "etf_prices_cache.json"
_PRICE_CACHE_TTL = 3600          # 1 hour — prices don't change minute-to-minute
_PRICE_CACHE_STALE_TTL = 86400   # 24 hours — use stale prices rather than fail
_YFINANCE_TIMEOUT = 8            # seconds — yfinance must answer within this window


def _load_price_cache(max_age: float | None = None) -> dict:
    import time
    if not _PRICE_CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(_PRICE_CACHE_PATH.read_text(encoding="utf-8"))
        age = time.time() - data.get("_cached_at", 0)
        if max_age is not None and age > max_age:
            return {}
        # Strip metadata before returning
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_price_cache(data: dict) -> None:
    import time
    data["_cached_at"] = time.time()
    _PRICE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PRICE_CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _fetch_price_yfinance(ticker: str, yf_ticker: str) -> float | None:
    """Fetch a single price from yfinance with a hard timeout.

    Runs the blocking yfinance call in a thread and waits at most
    _YFINANCE_TIMEOUT seconds.  Returns None on timeout or error.
    """
    import concurrent.futures, yfinance as yf

    def _do() -> float | None:
        try:
            info = yf.Ticker(yf_ticker).info
            return (
                info.get("regularMarketPrice")
                or info.get("previousClose")
                or info.get("navPrice")
            )
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_do)
        try:
            return future.result(timeout=_YFINANCE_TIMEOUT)
        except (concurrent.futures.TimeoutError, Exception):
            return None


def get_price(ticker: str) -> dict | None:
    """Return ``{"price": float, "currency": str, "stale": bool}`` or ``None``.

    1. If a fresh cache entry exists (< ``_PRICE_CACHE_TTL``), use it.
    2. If a stale cache entry exists (< ``_PRICE_CACHE_STALE_TTL``), try to
       refresh from yfinance but **always** fall back to the stale price.
    3. If no cache at all, try yfinance directly; return None on failure.
    """
    import time

    ticker = ticker.upper()
    now = time.time()

    # ── Fast path: fresh cache ──────────────────────────────────────────────
    fresh = _load_price_cache(max_age=_PRICE_CACHE_TTL)
    if ticker in fresh:
        return {"price": fresh[ticker]["price"], "currency": fresh[ticker].get("currency", "ZAR"), "stale": False}

    # ── Medium path: stale cache exists, try refresh but keep fallback ───────
    stale = _load_price_cache(max_age=_PRICE_CACHE_STALE_TTL)
    stale_entry = stale.get(ticker)
    stale_price = stale_entry.get("price") if stale_entry else None
    stale_currency = stale_entry.get("currency", "ZAR") if stale_entry else "ZAR"

    yf_ticker = ticker if "." in ticker else f"{ticker}.JO"
    fetched = _fetch_price_yfinance(ticker, yf_ticker)

    if fetched:
        currency = "ZAR" if ".JO" in yf_ticker else "USD"
        full_cache = _load_price_cache(max_age=float("inf"))
        full_cache[ticker] = {"price": fetched, "currency": currency}
        _save_price_cache(full_cache)
        return {"price": fetched, "currency": currency, "stale": False}

    if stale_price is not None:
        return {"price": stale_price, "currency": stale_currency, "stale": True}

    return None


# ── API routes ──────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "etf-tracker"}


@app.get("/api/etf/status/meta")
def etf_meta():
    return get_db_meta()


@app.get("/api/etf")
def list_etfs():
    codes = get_all_etf_codes()
    result = []
    for code in codes:
        info = get_etf_info(code)
        if info and not code.startswith("_"):
            result.append({
                "ticker": code,
                "name": info.get("name", code),
                "benchmark": info.get("benchmark", ""),
                "ter": info.get("ter", 0),
                "holding_count": len(info.get("holdings", [])),
                "last_refreshed": info.get("_last_refreshed"),
                "page_hash": info.get("_page_hash"),
            })
    return {"etfs": result}


@app.get("/api/etf/{ticker}")
def etf_detail(ticker: str):
    info = get_etf_info(ticker.upper())
    if not info:
        raise HTTPException(status_code=404, detail=f"ETF {ticker} not found")
    price = get_price(ticker)
    price_val = price["price"] if price else None
    return {
        "ticker": ticker.upper(),
        "name": info.get("name"),
        "benchmark": info.get("benchmark"),
        "ter": info.get("ter"),
        "current_price": price_val,
        "price_stale": price.get("stale", False) if price else None,
        "holdings": info.get("holdings", []),
        "holding_count": info.get("holding_count"),
        "last_refreshed": info.get("_last_refreshed"),
        "page_hash": info.get("_page_hash"),
    }


@app.get("/api/etf/{ticker}/raw")
def etf_raw_source(ticker: str):
    """Serve raw scraped source for an ETF."""
    ticker = ticker.upper()
    raw_path = _RAW_DIR / f"{ticker}.txt"
    if not raw_path.exists():
        raise HTTPException(status_code=404, detail="No raw source stored")
    return HTMLResponse(content=raw_path.read_text(encoding="utf-8"))


@app.post("/api/refresh")
async def trigger_refresh():
    """Invalidate cache so next request picks up fresh DB data."""
    _invalidate_cache()
    return {"status": "ok", "message": "Cache invalidated. Data will be reloaded on next request."}


# ── Portfolio routes ───────────────────────────────────────────────────────

@app.get("/api/portfolio")
def portfolio_summary():
    data = _load_portfolio()
    positions_out = []
    total_value = 0.0
    total_cost = 0.0
    for pos in data["positions"]:
        p = get_price(pos["etf_ticker"])
        price_val = p["price"] if p else None
        etf_info = get_etf_info(pos["etf_ticker"])
        value = pos["shares"] * (price_val or 0)
        cost = pos["shares"] * pos["cost_basis_per_share"]
        pnl = value - cost
        total_value += value
        total_cost += cost
        positions_out.append({
            "etf_ticker": pos["etf_ticker"],
            "etf_name": etf_info.get("name", pos["etf_ticker"]) if etf_info else pos["etf_ticker"],
            "shares": pos["shares"],
            "cost_basis_per_share": pos["cost_basis_per_share"],
            "last_price": price_val,
            "price_stale": p.get("stale", False) if p else None,
            "value_zar": round(value, 2),
            "cost_zar": round(cost, 2),
            "pnl_zar": round(pnl, 2),
            "pnl_pct": round(pnl / cost * 100, 2) if cost > 0 else 0,
            "ter": etf_info.get("ter", 0) if etf_info else 0,
        })
    for p in positions_out:
        p["weight_pct"] = round(p["value_zar"] / total_value * 100, 2) if total_value > 0 else 0
    return {
        "positions": positions_out,
        "total_value_zar": round(total_value, 2),
        "total_cost_zar": round(total_cost, 2),
        "total_pnl_zar": round(total_value - total_cost, 2),
        "total_pnl_pct": round((total_value - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0,
    }


@app.post("/api/portfolio/positions")
async def add_position(body: dict):
    ticker = body.get("etf_ticker", "").strip().upper()
    shares = float(body.get("shares", 0))
    cost = float(body.get("cost_basis_per_share", 0))
    currency = body.get("currency", "ZAR")
    if not ticker or shares <= 0:
        raise HTTPException(status_code=422, detail="etf_ticker and shares required")
    data = _load_portfolio()
    for pos in data["positions"]:
        if pos["etf_ticker"] == ticker:
            total = pos["shares"] + shares
            pos["cost_basis_per_share"] = round((pos["shares"] * pos["cost_basis_per_share"] + shares * cost) / total, 4)
            pos["shares"] = total
            _save_portfolio(data)
            return pos
    data["positions"].append({"etf_ticker": ticker, "shares": shares, "cost_basis_per_share": cost, "currency": currency})
    _save_portfolio(data)
    return data["positions"][-1]


@app.delete("/api/portfolio/positions/{etf_ticker}")
def remove_position(etf_ticker: str):
    data = _load_portfolio()
    original = len(data["positions"])
    data["positions"] = [p for p in data["positions"] if p["etf_ticker"] != etf_ticker.upper()]
    if len(data["positions"]) == original:
        raise HTTPException(status_code=404, detail="Position not found")
    _save_portfolio(data)
    return {"status": "deleted", "etf_ticker": etf_ticker.upper()}


@app.get("/api/portfolio/rollup")
def portfolio_rollup():
    from collections import defaultdict
    data = _load_portfolio()
    holdings_map = {}
    sector_map = defaultdict(float)
    total_value = sum(p["shares"] * (get_price(p["etf_ticker"]) or {}).get("price", 0) for p in data["positions"])
    for pos in data["positions"]:
        etf_info = get_etf_info(pos["etf_ticker"])
        if not etf_info:
            continue
        etf_value = pos["shares"] * (get_price(pos["etf_ticker"]) or {}).get("price", 0)
        etf_weight = etf_value / total_value if total_value > 0 else 0
        for h in etf_info.get("holdings", []):
            t = h["ticker"]
            w = h["weight"] / 100 * etf_weight * 100
            if t not in holdings_map:
                holdings_map[t] = {"ticker": t, "name": h["name"], "total_weight_pct": 0, "via_etfs": [], "sector": h.get("sector", "Unknown")}
            holdings_map[t]["total_weight_pct"] += w
            holdings_map[t]["via_etfs"].append({"etf_ticker": pos["etf_ticker"], "weight_pct": round(w, 4)})
            sector_map[h.get("sector", "Unknown")] += w
    consolidated = sorted(holdings_map.values(), key=lambda x: -x["total_weight_pct"])
    for h in consolidated:
        h["total_weight_pct"] = round(h["total_weight_pct"], 4)
    return {
        "consolidated_holdings": consolidated[:50],
        "sector_allocation": dict(sorted(sector_map.items(), key=lambda x: -x[1])),
        "top_10": consolidated[:10],
    }


# ── SPA fallback ────────────────────────────────────────────────────────────
if _FRONTEND_DIST.exists():
    @app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        index_file = _FRONTEND_DIST / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        raise HTTPException(status_code=404, detail="Frontend not built")