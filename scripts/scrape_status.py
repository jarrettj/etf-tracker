"""
scrape_status.py — Shared helper for tracking ETF scrape progress.

Both the FastAPI backend and the refresh scripts (refresh_holdings.py,
refresh_prices.py) import this to read/write a shared status file at
data/scrape_status.json.

Schema:
{
  "current_run": {
    "type": "holdings" | "prices",
    "started_at": "2026-06-01T22:00:00+02:00",
    "tickers_total": 6,
    "tickers_done": 3,
    "tickers": {
      "STXESG": {"status": "done", "source": "satrix_mdd", "holdings_found": 10, "error": null},
      "STXNDQ": {"status": "running", "source": null, "holdings_found": null, "error": null},
      "SYG4IR": {"status": "pending", "source": null, "holdings_found": null, "error": null},
      ...
    }
  },
  "last_runs": [
    {
      "type": "holdings",
      "started_at": "2026-05-25T09:00:00+02:00",
      "finished_at": "2026-05-25T09:02:30+02:00",
      "tickers_total": 6,
      "tickers_succeeded": 5,
      "tickers_failed": 1,
      "tickers": { ... }
    }
  ]
}
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCRAPE_STATUS_PATH = Path(__file__).parent.parent / "data" / "scrape_status.json"
MAX_RUNS_HISTORY = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    if not SCRAPE_STATUS_PATH.exists():
        return {"current_run": None, "last_runs": []}
    try:
        return json.loads(SCRAPE_STATUS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"current_run": None, "last_runs": []}


def _save(data: dict) -> None:
    SCRAPE_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCRAPE_STATUS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def start_run(run_type: str, tickers: list[str]) -> None:
    """Mark a new scrape run as started."""
    data = _load()
    # If there's already a current run, move it to history first
    if data.get("current_run"):
        _archive_current(data)
    ticker_states = {t: {"status": "pending", "source": None, "holdings_found": None, "error": None} for t in tickers}
    data["current_run"] = {
        "type": run_type,
        "started_at": _now(),
        "finished_at": None,
        "tickers_total": len(tickers),
        "tickers_done": 0,
        "tickers_succeeded": 0,
        "tickers_failed": 0,
        "tickers": ticker_states,
    }
    _save(data)


def update_ticker(ticker: str, status: str, source: str | None = None, holdings_found: int | None = None, error: str | None = None) -> None:
    """Update the status of a single ticker in the current run."""
    data = _load()
    run = data.get("current_run")
    if not run:
        return
    if ticker not in run["tickers"]:
        run["tickers"][ticker] = {"status": "pending", "source": None, "holdings_found": None, "error": None}
    entry = run["tickers"][ticker]
    entry["status"] = status
    if source is not None:
        entry["source"] = source
    if holdings_found is not None:
        entry["holdings_found"] = holdings_found
    if error is not None:
        entry["error"] = error
    if status in ("done", "failed"):
        run["tickers_done"] = run.get("tickers_done", 0) + 1
        if status == "done":
            run["tickers_succeeded"] = run.get("tickers_succeeded", 0) + 1
        else:
            run["tickers_failed"] = run.get("tickers_failed", 0) + 1
    _save(data)


def finish_run() -> None:
    """Mark the current run as finished and archive it."""
    data = _load()
    run = data.get("current_run")
    if not run:
        return
    run["finished_at"] = _now()
    _archive_current(data)
    _save(data)


def _archive_current(data: dict) -> None:
    run = data.get("current_run")
    if not run:
        return
    data.setdefault("last_runs", [])
    data["last_runs"].insert(0, run)
    data["last_runs"] = data["last_runs"][:MAX_RUNS_HISTORY]
    data["current_run"] = None


def get_status() -> dict:
    """Return the full scrape status (current run + history)."""
    return _load()


def get_current_run() -> Optional[dict]:
    """Return just the current run, or None."""
    data = _load()
    return data.get("current_run")
