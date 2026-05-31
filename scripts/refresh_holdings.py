#!/usr/bin/env python3
"""
refresh_holdings.py — Refresh ETF holdings by re-scraping fact sheets.

Since JSE ETF holdings aren't available via free API, this script documents
the refresh process. Run it to check status, then ask the Hermes agent
to perform the actual web scraping when needed.

Usage:
    python scripts/refresh_holdings.py --status   # Show DB status
    python scripts/refresh_holdings.py --check    # Check if updates needed
    python scripts/refresh_holdings.py --refresh  # Instructions for manual refresh
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "data" / "etf_holdings_db.json"

ETF_CONFIG = {
    "STXESG": {
        "name": "Satrix MSCI World ESG Enhanced Feeder ETF",
        "search": "Satrix MSCI World ESG Enhanced Feeder ETF STXESG top holdings",
        "ter": 0.34,
    },
    "STXNDQ": {
        "name": "Satrix Nasdaq 100 ETF",
        "search": "Satrix Nasdaq 100 ETF STXNDQ top holdings",
        "ter": 0.45,
    },
    "SYG4IR": {
        "name": "Sygnia Itrix 4th Industrial Revolution Global Equity AMETF",
        "search": "Sygnia 4th Industrial Revolution SYG4IR top holdings",
        "ter": 0.64,
    },
    "SYGEU": {
        "name": "Sygnia Itrix Euro Stoxx 50 ETF",
        "search": "Sygnia Euro Stoxx 50 SYGEU top holdings",
        "ter": 0.91,
    },
    "SYGUS": {
        "name": "Sygnia Itrix MSCI USA Index ETF",
        "search": "Sygnia MSCI USA SYGUS top holdings",
        "ter": 0.89,
    },
    "SYGESG": {
        "name": "Sygnia Itrix S&P Global 1200 ESG ETF",
        "search": "Sygnia S&P Global 1200 ESG SYGESG top holdings",
        "ter": 0.37,
    },
}


def load_db() -> dict:
    if DB_PATH.exists():
        with open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def status(db: dict):
    print("ETF Holdings Database Status")
    print("=" * 60)
    for ticker, config in ETF_CONFIG.items():
        if ticker in db:
            h_count = len(db[ticker].get("holdings", []))
            refreshed = db[ticker].get("_last_refreshed", "never")
            if refreshed and refreshed != "never":
                try:
                    dt = datetime.fromisoformat(refreshed.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - dt).days
                    refreshed = f"{refreshed[:10]} ({age}d ago)"
                except ValueError:
                    pass
            print(f"  {ticker:10s} {h_count:3d} holdings  refreshed: {refreshed}")
        else:
            print(f"  {ticker:10s} NOT IN DB")
    print(f"\nDB: {DB_PATH}")
    print(f"Updated: {db.get('_updated', 'unknown')}")


def check(db: dict) -> list[str]:
    needs_update = []
    for ticker in ETF_CONFIG:
        if ticker not in db:
            needs_update.append(ticker)
            continue
        last = db[ticker].get("_last_refreshed", "")
        if last:
            try:
                dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - dt).days
                if age > 90:
                    needs_update.append(ticker)
            except ValueError:
                needs_update.append(ticker)
        else:
            needs_update.append(ticker)
    return needs_update


def main():
    parser = argparse.ArgumentParser(description="ETF Holdings DB maintenance")
    parser.add_argument("--status", action="store_true", help="Show DB status")
    parser.add_argument("--check", action="store_true", help="Check if updates needed")
    parser.add_argument("--refresh", action="store_true", help="Show refresh instructions")
    args = parser.parse_args()

    db = load_db()

    if args.status or (not args.check and not args.refresh):
        status(db)

    if args.check:
        needs = check(db)
        if needs:
            print("Needs refresh (>90 days or missing):")
            for t in needs:
                last = db.get(t, {}).get("_last_refreshed", "never")
                print(f"  {t}: {last}")
        else:
            print("All ETFs up to date (refreshed within 90 days).")

    if args.refresh:
        print()
        print("=" * 60)
        print("REFRESH INSTRUCTIONS")
        print("=" * 60)
        print()
        print("Ask the Hermes agent to refresh holdings:")
        print()
        print('  "Refresh the ETF holdings database. Search for the latest')
        print('   fact sheets for STXESG, STXNDQ, SYG4IR, SYGEU, SYGUS,')
        print('   SYGESG and update data/etf_holdings_db.json with the')
        print('   latest top holdings from each."')
        print()
        print("The agent will use web search + PDF extraction to get")
        print("the latest data, same as the initial research.")
        print()


if __name__ == "__main__":
    main()
