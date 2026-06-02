#!/usr/bin/env python3
"""
refresh_holdings.py — ETF holdings refresh Helper.

Two modes:
  1. Agent-driven (recommended): Ask Hermes to scrape & refresh.
     The agent uses web_extract to pull holdings from JS-rendered pages,
     then runs this script with --update to write results.
  2. Self-serve --status: Show DB status (dates, sources, counts).

Usage:
    --status                  Show DB status
    --update TICKER JSON      Update one ETF from scraped JSON data
    --check                   List ETFs needing refresh (>90 days)
"""

import json, sys, argparse
from pathlib import Path
from datetime import datetime, timezone

# Shared scrape-status tracker (best-effort; never breaks a holdings update).
sys.path.insert(0, str(Path(__file__).parent))
try:
    import scrape_status
except Exception:  # pragma: no cover - tracking is best-effort
    scrape_status = None

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "data" / "etf_holdings_db.json"

ETF_SOURCES = {
    "STXESG": {
        "name": "Satrix MSCI World ESG Enhanced Feeder ETF",
        "url": "https://satrix.co.za/fund/mdd/STXESG",
        "ter": 0.34,
    },
    "STXNDQ": {
        "name": "Satrix Nasdaq 100 ETF",
        "url": "https://satrix.co.za/fund/mdd/STXNDQ",
        "ter": 0.45,
    },
    "SYG4IR": {
        "name": "Sygnia Itrix 4th Industrial Revolution Global Equity AMETF",
        "url": "https://www.sygnia.co.za/fund/sygnia-4th-industrial-revolution-global-equity-fund-class-a",
        "ter": 0.64,
    },
    "SYGEU": {
        "name": "Sygnia Itrix Euro Stoxx 50 ETF",
        "url": "https://www.sygnia.co.za/fund/sygnia-itrix-euro-stoxx-50-etf",
        "ter": 0.91,
    },
    "SYGUS": {
        "name": "Sygnia Itrix MSCI USA Index ETF",
        "url": "https://www.sygnia.co.za/fund/sygnia-itrix-msci-usa-index-etf",
        "ter": 0.89,
    },
    "SYGESG": {
        "name": "Sygnia Itrix S&P Global 1200 ESG ETF",
        "url": "https://www.sygnia.co.za/fund/sygnia-itrix-s-p-global-1200-esg-etf",
        "ter": 0.37,
    },
}


def load_db() -> dict:
    if DB_PATH.exists():
        with open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_db(db: dict) -> None:
    db["_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
        f.write("\n")


def status(db: dict) -> None:
    print("ETF Holdings Database Status")
    print("=" * 65)
    now = datetime.now(timezone.utc)
    for ticker, src in ETF_SOURCES.items():
        if ticker in db:
            h_count = len(db[ticker].get("holdings", []))
            refreshed = db[ticker].get("_last_refreshed", "never")
            url = db[ticker].get("_source_url", "—")
            if refreshed and refreshed != "never":
                try:
                    dt = datetime.strptime(refreshed[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    age = (now - dt).days
                    refreshed = f"{refreshed[:10]} ({age}d ago)"
                except ValueError:
                    pass
            print(f"  {ticker:10s} {h_count:3d} holdings  refreshed: {refreshed}")
            print(f"             source: {url[:75]}")
        else:
            print(f"  {ticker:10s} NOT IN DB")
    print(f"\nDB: {DB_PATH}")
    print(f"_updated: {db.get('_updated', 'unknown')}")
    print(f"_source:  {db.get('_source', 'unknown')}")


def check(db: dict) -> list:
    needs = []
    now = datetime.now(timezone.utc)
    for ticker in ETF_SOURCES:
        if ticker not in db:
            needs.append((ticker, "missing"))
            continue
        last = db[ticker].get("_last_refreshed", "")
        if last:
            try:
                dt = datetime.strptime(last[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                age = (now - dt).days
                if age > 90:
                    needs.append((ticker, f"{age}d old"))
            except ValueError:
                needs.append((ticker, "bad date"))
        else:
            needs.append((ticker, "never"))
    return needs


def update_etf(db: dict, ticker: str, holdings: list) -> None:
    """Update a single ETF's holdings from scraped data."""
    src = ETF_SOURCES[ticker]
    refresh_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = db.get(ticker, {})
    db[ticker] = {
        **existing,
        "name": src["name"],
        "benchmark": existing.get("benchmark", ""),
        "ter": src["ter"],
        "holdings": holdings,
        "_source_url": src["url"],
        "_last_refreshed": refresh_date,
    }
    if scrape_status is not None:
        try:
            scrape_status.update_ticker(ticker, "done", source="agent", holdings_found=len(holdings))
        except Exception:  # pragma: no cover - tracking is best-effort
            pass
    print(f"  Updated {ticker}: {len(holdings)} holdings, _last_refreshed={refresh_date}")


def main():
    parser = argparse.ArgumentParser(description="ETF Holdings DB maintenance")
    parser.add_argument("--status", action="store_true", help="Show DB status")
    parser.add_argument("--check", action="store_true", help="List ETFs needing refresh")
    parser.add_argument("--update", nargs=2, metavar=("TICKER", "JSON"),
                        help="Update ETF from scraped JSON string")
    args = parser.parse_args()
    db = load_db()

    if args.status or (not args.update and not args.check):
        status(db)
        return

    if args.check:
        needs = check(db)
        if needs:
            print("ETFs needing refresh:")
            for ticker, reason in needs:
                last = db.get(ticker, {}).get("_last_refreshed", "never")
                print(f"  {ticker:10s}  {reason:10s}  (last: {last})")
        else:
            print("All ETFs up to date (refreshed within 90 days).")
        return

    if args.update:
        ticker = args.update[0].upper().strip()
        if ticker not in ETF_SOURCES:
            print(f"Unknown ETF: {ticker}")
            sys.exit(1)
        try:
            holdings = json.loads(args.update[1])
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
            sys.exit(1)
        update_etf(db, ticker, holdings)
        save_db(db)
        print(f"Database saved to {DB_PATH}")


if __name__ == "__main__":
    main()
