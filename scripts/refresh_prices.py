#!/usr/bin/env python3
"""
refresh_prices.py — ETF price cache updater.

Writes latest prices to ~/.tradingagents/etf_prices_cache.json which the
FastAPI server reads from.  Designed to be called by a cron job, NOT by
the server itself (the server only reads the cache; this script writes it).

Falls back through multiple sources per-ticker:
  1. JSE website (MarketWatch page — HTML table, no JS required)
  2. AVMF (African Volatility Market Data) JSON API
  3. Yahoo Finance (same yfinance call the server would use, but with timeout)
  4. Reuse existing cache entry even if old (better than nothing)

Usage:
    python scripts/refresh_prices.py                  # refresh all known ETFs
    python scripts/refresh_prices.py STXESG STXNDQ    # refresh specific tickers
    python scripts/refresh_prices.py --no-yfinance    # skip Yahoo Finance fallback
"""

import json, sys, argparse, time, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

# Shared scrape-status tracker (writes data/scrape_status.json so the backend's
# /api/status/scrape endpoint can surface progress). Imported defensively so a
# status-tracking problem never breaks the actual price refresh.
sys.path.insert(0, str(Path(__file__).parent))
try:
    import scrape_status
except Exception:  # pragma: no cover - tracking is best-effort
    scrape_status = None

PRICE_CACHE_PATH = Path.home() / ".tradingagents" / "etf_prices_cache.json"

# Ticker -> (display name, JSE_MW path or None)
TICKERS = {
    "STXESG": ("Satrix MSCI World ESG Enhanced Feeder ETF", "satrix-msci-world-esg-enhanced-feeder-etf"),
    "STXNDQ": ("Satrix Nasdaq 100 ETF", "satrix-nasdaq-100-etf"),
    "SYG4IR": ("Sygnia Itrix 4th Industrial Revolution", None),
    "SYGEU":  ("Sygnia Itrix Euro Stoxx 50 ETF", None),
    "SYGUS":  ("Sygnia Itrix MSCI USA Index ETF", None),
    "SYGESG": ("Sygnia Itrix S&P Global 1200 ESG ETF", None),
}


def _track(fn_name: str, *args, **kwargs) -> None:
    """Best-effort call into scrape_status; never raises into the refresh flow."""
    if scrape_status is None:
        return
    try:
        getattr(scrape_status, fn_name)(*args, **kwargs)
    except Exception:  # pragma: no cover - tracking is best-effort
        pass


def _load_existing_cache() -> dict:
    if not PRICE_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(PRICE_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(data: dict) -> None:
    data["_cached_at"] = time.time()
    PRICE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRICE_CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _jse_mw_price(ticker: str, mw_slug: str | None) -> float | None:
    """Scrape the JSE MarketWatch page for the last traded price."""
    if not mw_slug:
        return None
    url = f"https://www.jse.co.za/market-data/equities/company-information/{mw_slug}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Look for price in meta or JSON-LD
        import re
        # Try JSON-LD first
        for m in re.finditer(r'"price"\s*:\s*"?(\d+\.?\d*)"?', html):
            val = float(m.group(1))
            if val > 100:  # JSE ETF prices are in cents (e.g. 9730 = R97.30)
                return val / 100.0
        # Try meta tag
        m = re.search(r'<meta[^>]+price[^>]+content="(\d+\.?\d*)"', html, re.I)
        if m:
            return float(m.group(1)) / 100.0
    except Exception:
        pass
    return None


def _avmf_price(ticker: str) -> float | None:
    """Try the AVMF JSON API (JSE data aggregator)."""
    url = f"https://api.amvm.co.za/v1/nav/{ticker}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        nav = data.get("nav") or data.get("NavPrice") or data.get("lastPrice")
        if nav:
            return float(nav)
    except Exception:
        pass
    return None


def _yfinance_price(ticker: str) -> float | None:
    """Fetch from yfinance with a thread-level timeout."""
    import concurrent.futures
    yf_ticker = f"{ticker}.JO"

    def _do():
        try:
            import yfinance as yf
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
            return future.result(timeout=8)
        except Exception:
            return None


def refresh_ticker(ticker: str, use_yfinance: bool = True, existing: dict | None = None) -> dict:
    """Try all sources for one ticker.  Returns dict with price, currency, source."""
    result = {"price": None, "currency": "ZAR", "source": None}
    name, mw_slug = TICKERS.get(ticker, (ticker, None))

    # 1. JSE MarketWatch
    price = _jse_mw_price(ticker, mw_slug)
    if price:
        result.update({"price": round(price, 2), "source": "jse_mw"})
        return result

    # 2. AVMF API
    price = _avmf_price(ticker)
    if price:
        result.update({"price": round(price, 2), "source": "avmf"})
        return result

    # 3. Yahoo finance
    if use_yfinance:
        price = _yfinance_price(ticker)
        if price:
            result.update({"price": round(price, 2), "source": "yfinance"})
            return result

    # 4. Fallback: reuse existing cache entry
    existing_entry = (existing or {}).get(ticker)
    if existing_entry and existing_entry.get("price"):
        result.update({"price": existing_entry["price"], "currency": existing_entry.get("currency", "ZAR"), "source": "stale_cache"})

    return result


def main():
    parser = argparse.ArgumentParser(description="Refresh ETF price cache")
    parser.add_argument("tickers", nargs="*", help="Specific tickers (default: all)")
    parser.add_argument("--no-yfinance", action="store_true", help="Skip Yahoo Finance fallback")
    args = parser.parse_args()

    target_tickers = [t.upper() for t in args.tickers] or list(TICKERS.keys())
    existing = _load_existing_cache()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    cache = _load_existing_cache()
    updated = 0
    skipped = 0

    known = [t for t in target_tickers if t in TICKERS]
    _track("start_run", "prices", known)

    for ticker in target_tickers:
        if ticker not in TICKERS:
            print(f"  SKIP {ticker}: not in TICKERS table")
            continue

        result = refresh_ticker(ticker, use_yfinance=not args.no_yfinance, existing=cache)
        if result["price"]:
            entry = {"price": result["price"], "currency": result["currency"]}
            cache[ticker] = entry
            tag = "⚠️ STALE" if result["source"] == "stale_cache" else "✓"
            print(f"  {tag} {ticker}: {result['price']} {result['currency']} (via {result['source']})")
            updated += 1
            _track("update_ticker", ticker, "done", source=result["source"])
        else:
            print(f"  ✗ {ticker}: no price from any source")
            skipped += 1
            _track("update_ticker", ticker, "failed", error="no price from any source")

    _track("finish_run")
    _save_cache(cache)
    print(f"\n  Saved {updated} prices to {PRICE_CACHE_PATH}  [{now_str}]")
    if skipped:
        print(f"  {skipped} tickers still have no price data")


if __name__ == "__main__":
    main()
