"""ETF Tracker — Connectivity / smoke tests.

These tests verify a LIVE server is actually running and responding correctly.
They make real HTTP requests to the backend — start the server first:

    make start-backend    # or however you start it

Set the env var BACKEND_URL if the server is not on localhost:8002:
    BACKEND_URL=http://localhost:8003 pytest tests/test_smoke.py -v
"""

import os
import urllib.request
import urllib.error
import json

BASE = os.environ.get("BACKEND_URL", "http://localhost:8002")


def _fetch(method, path, data=None, expect_code=200):
    """Helper: make HTTP request to BASE+path, return parsed JSON."""
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == expect_code, f"Expected {expect_code}, got {resp.status} for {path}"
            return json.loads(resp.read())
    except urllib.error.URLError as exc:
        pytest.fail(f"Cannot connect to {url}: {exc}")


# ── Server is reachable ─────────────────────────────────────────────────────

def test_health():
    """Server responds to /api/health."""
    resp = _fetch("GET", "/api/health")
    assert resp.get("status") == "ok"
    assert resp.get("app") == "etf-tracker"


def test_etf_list():
    """Server returns the 6 known ETFs."""
    resp = _fetch("GET", "/api/etf")
    etfs = resp.get("etfs", [])
    assert len(etfs) == 6, f"Expected 6 ETFs, got {len(etfs)}"
    tickers = {e["ticker"] for e in etfs}
    expected = {"STXNDQ", "STXESG", "SYG4IR", "SYGEU", "SYGUS", "SYGESG"}
    assert tickers == expected, f"Missing ETFs: {expected - tickers}"


def test_etf_detail():
    """Server returns detail for a known ETF."""
    resp = _fetch("GET", "/api/etf/STXNDQ")
    assert resp["ticker"] == "STXNDQ"
    assert resp["name"] == "Satrix Nasdaq 100 ETF"
    assert isinstance(resp.get("holdings"), list)
    assert len(resp["holdings"]) > 0


def test_portfolio_empty():
    """Portfolio returns empty when no positions added."""
    resp = _fetch("GET", "/api/portfolio")
    assert resp.get("positions") == []
    assert resp["total_value_zar"] == 0.0


def test_portfolio_crud():
    """Add a position, verify it shows, then delete it."""
    # Add
    add = _fetch("POST", "/api/portfolio/positions", {
        "etf_ticker": "STXNDQ",
        "shares": 10,
        "cost_basis_per_share": 150.00,
    })
    assert add["etf_ticker"] == "STXNDQ"

    # Verify it appears
    portfolio = _fetch("GET", "/api/portfolio")
    tickers = [p["etf_ticker"] for p in portfolio["positions"]]
    assert "STXNDQ" in tickers

    # Delete
    deleted = _fetch("DELETE", "/api/portfolio/positions/STXNDQ")
    assert deleted["status"] == "deleted"

    # Verify gone
    portfolio = _fetch("GET", "/api/portfolio")
    tickers = [p["etf_ticker"] for p in portfolio["positions"]]
    assert "STXNDQ" not in tickers


def test_portfolio_rollup():
    """Rollup is valid JSON even when empty."""
    resp = _fetch("GET", "/api/portfolio/rollup")
    assert "consolidated_holdings" in resp
    assert "sector_allocation" in resp


# ── Frontend (Vite dev server) ──────────────────────────────────────────────

FRONTEND_BASE = os.environ.get("FRONTEND_URL", "http://localhost:5174")


def test_frontend_serves_html():
    """Vite dev server responds with HTML (SPA shell)."""
    url = FRONTEND_BASE + "/"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        body = resp.read().decode()
        assert "<title>ETF Tracker</title>" in body
        assert "root" in body  # React mount point


def test_frontend_api_proxy():
    """Vite dev server proxies /api/health to backend correctly."""
    url = FRONTEND_BASE + "/api/health"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
        assert data["status"] == "ok"
