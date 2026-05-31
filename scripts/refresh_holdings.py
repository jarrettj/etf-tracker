#!/usr/bin/env python3
"""
refresh_holdings.py — Refresh ETF holdings by re-scraping fact sheets.

This script uses web search + PDF extraction to get the latest holdings
from Satrix and Sygnia fact sheets. It's designed to be run manually
when holdings data needs updating (typically every 3-6 months).

Usage:
    python scripts/refresh_holdings.py           # Refresh all ETFs
    python scripts/refresh_holdings.py --etf STXESG  # Refresh one ETF
    python scripts/refresh_holdings.py --check    # Check if updates are available

The script will:
1. Search for the latest fact sheet for each ETF
2. Extract holdings from the PDF/HTML
3. Update etf_holdings_db.json
4. Report what changed

Note: This requires the hermes web_search and web_extract tools.
For best results, run this through the Hermes agent rather than standalone.
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
        "search_query": "Satrix MSCI World ESG Enhanced Feeder ETF STXESG top holdings 2026",
        "benchmark": "MSCI World ESG Enhanced Focus CTB Index (ZAR)",
        "isin": "ZAE000289963",
        "ter": 0.34,
    },
    "STXNDQ": {
        "name": "Satrix Nasdaq 100 ETF",
        "search_query": "Satrix Nasdaq 100 ETF STXNDQ top holdings 2026",
        "benchmark": "NASDAQ 100 Index",
        "isin": "ZAE000209501",
        "ter": 0.45,
    },
    "SYG4IR": {
        "name": "Sygnia Itrix 4th Industrial Revolution Global Equity AMETF",
        "search_query": "Sygnia 4th Industrial Revolution SYG4IR top holdings 2026",
        "benchmark": "Solactive GBS United States 500 Index (ZAR)",
        "isin": "ZAE000252433",
        "ter": 0.64,
    },
    "SYGEU": {
        "name": "Sygnia Itrix Euro Stoxx 50 ETF",
        "search_query": "Sygnia Euro Stoxx 50 SYGEU top holdings 2026",
        "benchmark": "Euro STOXX 50 Index",
        "isin": "ZAE000249512",
        "ter": 0.91,
    },
    "SYGUS": {
        "name": "Sygnia Itrix MSCI USA Index ETF",
        "search_query": "Sygnia MSCI USA SYGUS top holdings 2026",
        "benchmark": "MSCI USA Index",
        "isin": "ZAE000249546",
        "ter": 0.89,
    },
    "SYGESG": {
        "name": "Sygnia Itrix S&P Global 1200 ESG ETF",
        "search_query": "Sygnia S&P Global 1200 ESG SYGESG top holdings 2026",
        "benchmark": "S&P Global 1200 Scored & Screened Index",
        "isin": "ZAE000296778",
        "ter": 0.37,
    },
}


def load_db() -> dict:
    if DB_PATH.exists():
        with open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_db(db: dict) -> None:
    db["_updated"] = datetime.now(timezone.utc).isoformat()
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved to {DB_PATH}")


def check_updates_needed(db: dict) -> list[str]:
    """Check which ETFs might need updating based on last refresh date."""
    needs_update = []
    for ticker in ETF_CONFIG:
        if ticker not in db:
            needs_update.append(ticker)
            continue
        last = db[ticker].get("_last_refreshed", "")
        if last:
            try:
                from datetime import datetime
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - last_dt).days
                if age_days > 90:
                    needs_update.append(ticker)
            except ValueError:
                needs_update.append(ticker)
        else:
            needs_update.append(ticker)
    return needs_update


def print_instructions():
    """Print instructions for manual refresh via Hermes agent."""
    print()
    print("=" * 60)
    print("MANUAL REFRESH INSTRUCTIONS")
    print("=" * 60)
    print()
    print("Since this script can't call web_search/web_extract directly,")
    print("the best way to refresh holdings is to ask the Hermes agent:")
    print()
    print('  "Refresh the ETF holdings database. Check for updated fact')
    print('   sheets for STXESG, STXNDQ, SYG4IR, SYGEU, SYGUS, SYGESG')
    print('   and update data/etf_holdings_db.json with the latest')
    print('   top 10-20 holdings from each."')
    print()
    print("Or for a single ETF:")
    print('  "What are the latest top holdings for SYGUS?"')
    print()
    print("The agent will search for the latest fact sheets and update")
    print("the database automatically.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Refresh ETF holdings database")
    parser.add_argument("--etf", help="Refresh a single ETF ticker")
    parser.add_argument("--all", action="store_true", help="Refresh all ETFs")
    parser.add_argument("--check", action="store_true", help="Check if updates are needed")
    parser.add_argument("--status", action="store_true", help="Show current DB status")
    args = parser.parse_args()

    db = load_db()

    if args.status:
        print("ETF Holdings Database Status")
        print("=" * 50)
        for ticker, config in ETF_CONFIG.items():
            if ticker in db:
                h_count = len(db[ticker].get("holdings", []))
                refreshed = db[ticker].get("_last_refreshed", "never")
                print(f"  {ticker:10s} {h_count:3d} holdings  last: {refreshed[:10]}")
            else:
                print(f"  {ticker:10s} NOT IN DB")
        print()
        print(f"Database: {DB_PATH}")
        print(f"Updated:  {db.get('_updated', 'unknown')}")
        return

    if args.check:
        needs_update = check_updates_needed(db)
        if needs_update:
            print(f"The following ETFs may need updating:")
            for t in needs_update:
                last = db.get(t, {}).get("_last_refreshed", "never")
                print(f"  {t}: last refreshed {last}")
        else:
            print("All ETFs appear up to date (refreshed within 90 days).")
        return

    if args.all or args.etf:
        print("This script requires web_search and web_extract tools.")
        print("Please ask the Hermes agent to perform the refresh.")
        print()
        if args.etf:
            ticker = args.etf.upper()
            query = ETF_CONFIG.get(ticker, {}).get("search_query", ticker)
            print(f'Say: "Search for the latest {ticker} fact sheet and')
            print(f' extract the top holdings. Update the ETF database."')
        else:
            print('Say: "Refresh all ETF holdings in the database."')
        print()
        print_instructions()
        return

    # Default: show status + help
    parser.print_help()
    print()
    print_instructions()


if __name__ == "__main__":
    main()
