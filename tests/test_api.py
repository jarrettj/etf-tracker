"""ETF Tracker — Full test suite.

Run with:  pytest tests/ -v
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary test database."""
    db = {
        "_comment": "Test DB",
        "STXNDQ": {
            "name": "Satrix Nasdaq 100 ETF",
            "benchmark": "NASDAQ 100 Index",
            "ter": 0.45,
            "holdings": [
                {"ticker": "NVDA", "name": "Nvidia Corp", "weight": 8.59, "sector": "Information Technology"},
                {"ticker": "AAPL", "name": "Apple Inc", "weight": 7.06, "sector": "Information Technology"},
                {"ticker": "MSFT", "name": "Microsoft Corp", "weight": 5.36, "sector": "Information Technology"},
            ],
        },
        "STXESG": {
            "name": "Satrix MSCI World ESG Enhanced Feeder ETF",
            "benchmark": "MSCI World ESG Enhanced Select Index",
            "ter": 0.34,
            "holdings": [],
        },
        "SYGUS": {
            "name": "Sygnia Itrix MSCI USA Index ETF",
            "benchmark": "MSCI USA Index",
            "ter": 0.89,
            "holdings": [
                {"ticker": "AAPL", "name": "Apple Inc", "weight": 4.20, "sector": "Information Technology"},
                {"ticker": "NVDA", "name": "Nvidia Corp", "weight": 2.50, "sector": "Information Technology"},
            ],
        },
    }
    db_file = tmp_path / "test_etf_holdings_db.json"
    db_file.write_text(json.dumps(db), encoding="utf-8")
    return db_file


@pytest.fixture
def portfolio_path(tmp_path):
    """Return a temporary portfolio path."""
    return tmp_path / "etf_portfolio.json"


@pytest.fixture
def price_cache_path(tmp_path):
    """Return a temporary price cache path."""
    return tmp_path / "etf_prices_cache.json"


@pytest.fixture
def client(test_db_path, portfolio_path, price_cache_path):
    """Create a TestClient with isolated temp paths."""
    import server.main as m

    # Patch all paths before creating the client
    m._HOLDINGS_DB_PATH = test_db_path
    m._PORTFOLIO_PATH = portfolio_path
    m._PRICE_CACHE_PATH = price_cache_path
    m._holdings_cache = None

    from server.main import app
    with TestClient(app) as tc:
        yield tc


# ── Health Check ─────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "app": "etf-tracker"}


# ── ETF Listing ──────────────────────────────────────────────────────────────

class TestEtfListing:
    def test_list_etfs_returns_all(self, client):
        resp = client.get("/api/etf")
        assert resp.status_code == 200
        data = resp.json()
        assert "etfs" in data
        tickers = [e["ticker"] for e in data["etfs"]]
        assert "STXNDQ" in tickers
        assert "STXESG" in tickers
        assert "SYGUS" in tickers

    def test_list_etfs_excludes_meta_keys(self, client):
        resp = client.get("/api/etf")
        tickers = [e["ticker"] for e in resp.json()["etfs"]]
        assert "_comment" not in tickers

    def test_list_etfs_includes_holding_count(self, client):
        resp = client.get("/api/etf")
        stxndq = next(e for e in resp.json()["etfs"] if e["ticker"] == "STXNDQ")
        assert stxndq["holding_count"] == 3

    def test_list_etfs_empty_holdings(self, client):
        resp = client.get("/api/etf")
        stxesg = next(e for e in resp.json()["etfs"] if e["ticker"] == "STXESG")
        assert stxesg["holding_count"] == 0


# ── ETF Detail ───────────────────────────────────────────────────────────────

class TestEtfDetail:
    def test_etf_detail_found(self, client):
        resp = client.get("/api/etf/STXNDQ")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "STXNDQ"
        assert data["name"] == "Satrix Nasdaq 100 ETF"
        assert data["ter"] == 0.45
        assert len(data["holdings"]) == 3

    def test_etf_detail_case_insensitive(self, client):
        resp = client.get("/api/etf/stxndq")
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "STXNDQ"

    def test_etf_detail_not_found(self, client):
        resp = client.get("/api/etf/XXXX")
        assert resp.status_code == 404

    def test_etf_detail_holdings_structure(self, client):
        resp = client.get("/api/etf/STXNDQ")
        holdings = resp.json()["holdings"]
        assert holdings[0]["ticker"] == "NVDA"
        assert holdings[0]["name"] == "Nvidia Corp"
        assert holdings[0]["weight"] == 8.59
        assert holdings[0]["sector"] == "Information Technology"


# ── Portfolio: Empty State ───────────────────────────────────────────────────

class TestPortfolioEmpty:
    def test_empty_portfolio(self, client):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["positions"] == []
        assert data["total_value_zar"] == 0.0
        assert data["total_cost_zar"] == 0.0
        assert data["total_pnl_zar"] == 0.0
        assert data["total_pnl_pct"] == 0.0


# ── Portfolio: Add Position ──────────────────────────────────────────────────

class TestPortfolioAdd:
    def test_add_position(self, client):
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 50.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["etf_ticker"] == "STXNDQ"
        assert data["shares"] == 100
        assert data["cost_basis_per_share"] == 50.0

    def test_add_position_persists(self, client):
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 50.0,
        })
        resp = client.get("/api/portfolio")
        assert len(resp.json()["positions"]) == 1

    def test_add_position_case_insensitive(self, client):
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "stxndq",
            "shares": 50,
            "cost_basis_per_share": 30.0,
        })
        assert resp.status_code == 200
        assert resp.json()["etf_ticker"] == "STXNDQ"

    def test_add_position_missing_ticker(self, client):
        resp = client.post("/api/portfolio/positions", json={
            "shares": 100,
            "cost_basis_per_share": 50.0,
        })
        assert resp.status_code == 422

    def test_add_position_zero_shares(self, client):
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 0,
            "cost_basis_per_share": 50.0,
        })
        assert resp.status_code == 422

    def test_add_position_negative_shares(self, client):
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": -10,
            "cost_basis_per_share": 50.0,
        })
        assert resp.status_code == 422

    def test_add_position_default_currency(self, client):
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 10,
            "cost_basis_per_share": 20.0,
        })
        assert resp.json()["currency"] == "ZAR"

    def test_add_position_custom_currency(self, client):
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 10,
            "cost_basis_per_share": 20.0,
            "currency": "USD",
        })
        assert resp.json()["currency"] == "USD"

    def test_add_existing_position_averages_cost(self, client):
        """Adding to an existing position should use weighted average cost basis."""
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 50.0,
        })
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 60.0,
        })
        data = resp.json()
        assert data["shares"] == 200
        assert data["cost_basis_per_share"] == 55.0  # (100*50 + 100*60) / 200

    def test_add_multiple_different_etfs(self, client):
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 50.0,
        })
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXESG",
            "shares": 200,
            "cost_basis_per_share": 30.0,
        })
        resp = client.get("/api/portfolio")
        assert len(resp.json()["positions"]) == 2


# ── Portfolio: Remove Position ───────────────────────────────────────────────

class TestPortfolioRemove:
    def test_remove_position(self, client):
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 50.0,
        })
        resp = client.delete("/api/portfolio/positions/STXNDQ")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        assert resp.json()["etf_ticker"] == "STXNDQ"

    def test_remove_position_persists(self, client):
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 50.0,
        })
        client.delete("/api/portfolio/positions/STXNDQ")
        resp = client.get("/api/portfolio")
        assert resp.json()["positions"] == []

    def test_remove_nonexistent_position(self, client):
        resp = client.delete("/api/portfolio/positions/XXXX")
        assert resp.status_code == 404

    def test_remove_case_insensitive(self, client):
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 50.0,
        })
        resp = client.delete("/api/portfolio/positions/stxndq")
        assert resp.status_code == 200


# ── Portfolio: Edit Position (PUT) ───────────────────────────────────────────

class TestPortfolioEdit:
    def _add(self, client, shares=100, cost=50.0):
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": shares,
            "cost_basis_per_share": cost,
        })

    def test_edit_replaces_values(self, client):
        """PUT overwrites shares + cost (replace semantics, not averaging)."""
        self._add(client, shares=100, cost=50.0)
        resp = client.put("/api/portfolio/positions/STXNDQ", json={
            "shares": 25,
            "cost_basis_per_share": 80.0,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["shares"] == 25
        assert body["cost_basis_per_share"] == 80.0

    def test_edit_persists(self, client):
        self._add(client, shares=100, cost=50.0)
        client.put("/api/portfolio/positions/STXNDQ", json={
            "shares": 25, "cost_basis_per_share": 80.0,
        })
        resp = client.get("/api/portfolio")
        pos = next(p for p in resp.json()["positions"] if p["etf_ticker"] == "STXNDQ")
        assert pos["shares"] == 25
        assert pos["cost_basis_per_share"] == 80.0

    def test_edit_case_insensitive(self, client):
        self._add(client)
        resp = client.put("/api/portfolio/positions/stxndq", json={
            "shares": 10, "cost_basis_per_share": 5.0,
        })
        assert resp.status_code == 200
        assert resp.json()["shares"] == 10

    def test_edit_nonexistent_returns_404(self, client):
        resp = client.put("/api/portfolio/positions/XXXX", json={
            "shares": 10, "cost_basis_per_share": 5.0,
        })
        assert resp.status_code == 404

    def test_edit_invalid_shares_returns_422(self, client):
        self._add(client)
        resp = client.put("/api/portfolio/positions/STXNDQ", json={
            "shares": 0, "cost_basis_per_share": 5.0,
        })
        assert resp.status_code == 422


# ── Refresh Prices ───────────────────────────────────────────────────────────

class TestRefreshPrices:
    def test_refresh_prices_no_cache(self, client):
        resp = client.post("/api/refresh-prices")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_refresh_prices_expires_cache(self, client):
        """After refresh-prices, a previously-fresh ticker re-fetches from the source."""
        from server.main import _save_price_cache
        _save_price_cache({"STXNDQ": {"price": 200.0, "currency": "ZAR"}})

        # Sanity: while fresh, a read does NOT hit the network.
        with patch("server.main._fetch_price") as mock_fetch:
            client.get("/api/etf/STXNDQ")
            mock_fetch.assert_not_called()

        resp = client.post("/api/refresh-prices")
        assert resp.json()["status"] == "ok"

        # Now the cache is stale -> the next read attempts a live fetch.
        with patch("server.main._fetch_price", return_value=300.0) as mock_fetch:
            client.get("/api/etf/STXNDQ")
            mock_fetch.assert_called_with("STXNDQ", "STXNDQ.JO")

    def test_refresh_prices_falls_back_to_stale_on_error(self, client):
        """If the live fetch fails after expiry, the stale cached value is still served."""
        from server.main import _save_price_cache
        _save_price_cache({"STXNDQ": {"price": 200.0, "currency": "ZAR"}})
        client.post("/api/refresh-prices")
        with patch("server.main._fetch_price", return_value=None):
            resp = client.get("/api/etf/STXNDQ")
            data = resp.json()
            assert data["current_price"] == 2.0      # 200 cents -> R2.00
            assert data["price_stale"] is True


# ── Price memoization ────────────────────────────────────────────────────────

class TestPriceMemoization:
    def test_rollup_calls_get_price_once_per_ticker(self, client):
        """portfolio_rollup must not call get_price more than once per unique ticker."""
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ", "shares": 10, "cost_basis_per_share": 50.0,
        })
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "SYGUS", "shares": 10, "cost_basis_per_share": 40.0,
        })
        with patch("server.main.get_price", return_value=100.0) as mock_gp:
            client.get("/api/portfolio/rollup")
        called = {c.args[0] for c in mock_gp.call_args_list}
        assert called == {"STXNDQ", "SYGUS"}
        assert mock_gp.call_count == 2

    def test_summary_calls_get_price_once_per_ticker(self, client):
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ", "shares": 10, "cost_basis_per_share": 50.0,
        })
        with patch("server.main.get_price", return_value=100.0) as mock_gp:
            client.get("/api/portfolio")
        assert mock_gp.call_count == 1


# ── Scrape Status ────────────────────────────────────────────────────────────

class TestScrapeStatus:
    def test_scrape_status_empty(self, client):
        resp = client.get("/api/status/scrape")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_run" in data
        assert "last_runs" in data

    def test_scrape_status_reflects_written_run(self, client, tmp_path, monkeypatch):
        """A run written via scrape_status is surfaced by /api/status/scrape."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import scrape_status
        monkeypatch.setattr(scrape_status, "SCRAPE_STATUS_PATH", tmp_path / "scrape_status.json")
        scrape_status.start_run("prices", ["STXNDQ", "STXESG"])
        scrape_status.update_ticker("STXNDQ", "done", source="yfinance")
        scrape_status.finish_run()

        resp = client.get("/api/status/scrape")
        data = resp.json()
        assert data["current_run"] is None
        assert len(data["last_runs"]) >= 1
        assert data["last_runs"][0]["type"] == "prices"
        assert data["last_runs"][0]["tickers"]["STXNDQ"]["status"] == "done"


# ── Portfolio: Summary Calculations ──────────────────────────────────────────

class TestPortfolioSummary:
    def test_portfolio_totals(self, client):
        """Test that portfolio totals are calculated correctly."""
        with patch("server.main.get_price", return_value=100.0):
            client.post("/api/portfolio/positions", json={
                "etf_ticker": "STXNDQ",
                "shares": 10,
                "cost_basis_per_share": 80.0,
            })
            resp = client.get("/api/portfolio")
            data = resp.json()
            assert data["total_cost_zar"] == 800.0
            assert data["total_pnl_zar"] == 200.0  # (100-80)*10
            assert data["total_pnl_pct"] == 25.0   # 200/800*100

    def test_portfolio_weight_calculation(self, client):
        """Test that weight percentages sum to 100%."""
        with patch("server.main.get_price", return_value=100.0):
            client.post("/api/portfolio/positions", json={
                "etf_ticker": "STXNDQ",
                "shares": 10,
                "cost_basis_per_share": 50.0,
            })
            client.post("/api/portfolio/positions", json={
                "etf_ticker": "STXESG",
                "shares": 10,
                "cost_basis_per_share": 50.0,
            })
            resp = client.get("/api/portfolio")
            positions = resp.json()["positions"]
            total_weight = sum(p["weight_pct"] for p in positions)
            assert abs(total_weight - 100.0) < 0.01

    def test_portfolio_pnl_negative(self, client):
        """Test negative P&L when price drops below cost."""
        with patch("server.main.get_price", return_value=40.0):
            client.post("/api/portfolio/positions", json={
                "etf_ticker": "STXNDQ",
                "shares": 10,
                "cost_basis_per_share": 50.0,
            })
            resp = client.get("/api/portfolio")
            data = resp.json()
            assert data["total_pnl_zar"] == -100.0
            assert data["total_pnl_pct"] == -20.0

    def test_portfolio_etf_name_included(self, client):
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 10,
            "cost_basis_per_share": 50.0,
        })
        resp = client.get("/api/portfolio")
        pos = resp.json()["positions"][0]
        assert pos["etf_name"] == "Satrix Nasdaq 100 ETF"

    def test_portfolio_ter_included(self, client):
        client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 10,
            "cost_basis_per_share": 50.0,
        })
        resp = client.get("/api/portfolio")
        pos = resp.json()["positions"][0]
        assert pos["ter"] == 0.45


# ── Portfolio Rollup ─────────────────────────────────────────────────────────

class TestPortfolioRollup:
    def test_rollup_empty_portfolio(self, client):
        resp = client.get("/api/portfolio/rollup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["consolidated_holdings"] == []
        assert data["sector_allocation"] == {}
        assert data["top_10"] == []

    def test_rollup_consolidates_holdings(self, client):
        """Test that holdings across ETFs are consolidated."""
        with patch("server.main.get_price", return_value=100.0):
            client.post("/api/portfolio/positions", json={
                "etf_ticker": "STXNDQ",
                "shares": 10,
                "cost_basis_per_share": 50.0,
            })
            client.post("/api/portfolio/positions", json={
                "etf_ticker": "SYGUS",
                "shares": 10,
                "cost_basis_per_share": 40.0,
            })
            resp = client.get("/api/portfolio/rollup")
            data = resp.json()
            # AAPL appears in both ETFs — should be consolidated
            aapl = next((h for h in data["consolidated_holdings"] if h["ticker"] == "AAPL"), None)
            assert aapl is not None
            assert len(aapl["via_etfs"]) == 2

    def test_rollup_sector_allocation(self, client):
        """Test sector allocation aggregation."""
        with patch("server.main.get_price", return_value=100.0):
            client.post("/api/portfolio/positions", json={
                "etf_ticker": "STXNDQ",
                "shares": 10,
                "cost_basis_per_share": 50.0,
            })
            resp = client.get("/api/portfolio/rollup")
            data = resp.json()
            assert "Information Technology" in data["sector_allocation"]

    def test_rollup_top_10_sorted(self, client):
        """Test that top 10 holdings are sorted by weight descending."""
        with patch("server.main.get_price", return_value=100.0):
            client.post("/api/portfolio/positions", json={
                "etf_ticker": "STXNDQ",
                "shares": 10,
                "cost_basis_per_share": 50.0,
            })
            resp = client.get("/api/portfolio/rollup")
            top_10 = resp.json()["top_10"]
            if len(top_10) >= 2:
                weights = [h["total_weight_pct"] for h in top_10]
                assert weights == sorted(weights, reverse=True)


# ── Price Cache ──────────────────────────────────────────────────────────────

class TestPriceCache:
    def test_price_cache_miss_fetches_from_source(self, client):
        """Test that cache miss triggers a live fetch.

        get_price returns a dict and, for a JSE (.JO) ticker, divides the
        cents price by 100 for display (150 cents -> R1.50).
        """
        with patch("server.main._fetch_price", return_value=150.0):
            from server.main import get_price
            price = get_price("STXNDQ")
            assert price["price"] == 1.5
            assert price["currency"] == "ZAR"
            assert price["stale"] is False

    def test_price_cache_hit_returns_cached(self, client):
        """Test that cache hit returns without a live fetch.

        Cached prices for .JO tickers are stored in cents and displayed in rand.
        """
        from server.main import _save_price_cache, get_price
        _save_price_cache({"STXNDQ": {"price": 200.0, "currency": "ZAR"}})

        with patch("server.main._fetch_price") as mock_fetch:
            price = get_price("STXNDQ")
            assert price["price"] == 2.0
            mock_fetch.assert_not_called()

    def test_price_jo_ticker(self, client):
        """Test that .JO tickers are used for SA ETFs."""
        with patch("server.main._fetch_price", return_value=50.0) as mock_fetch:
            from server.main import get_price
            get_price("STXNDQ")
            mock_fetch.assert_called_with("STXNDQ", "STXNDQ.JO")

    def test_fetch_price_parses_yahoo_chart(self, client):
        """_fetch_price reads Yahoo's chart meta, preferring regularMarketPrice
        then previousClose, and tolerates network failures by returning None."""
        from server import main

        def _resp(meta):
            payload = json.dumps({"chart": {"result": [{"meta": meta}]}}).encode()

            class _Ctx:
                def read(self_inner):
                    return payload

                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, *a):
                    return False

            return _Ctx()

        # regularMarketPrice wins when present (cents for .JO)
        with patch("urllib.request.urlopen", return_value=_resp(
                {"regularMarketPrice": 9730.0, "previousClose": 9600.0})):
            assert main._fetch_price("STXNDQ", "STXNDQ.JO") == 9730.0

        # falls back to previousClose
        with patch("urllib.request.urlopen", return_value=_resp({"previousClose": 75.0})):
            assert main._fetch_price("TEST", "TEST.JO") == 75.0

        # network error -> None
        with patch("urllib.request.urlopen", side_effect=Exception("network")):
            assert main._fetch_price("STXNDQ", "STXNDQ.JO") is None

    def test_price_returns_none_on_error(self, client):
        """Test that price returns None when the live fetch fails and no cache exists."""
        with patch("server.main._fetch_price", return_value=None):
            from server.main import get_price
            price = get_price("STXNDQ")
            assert price is None


# ── Holdings DB ──────────────────────────────────────────────────────────────

class TestHoldingsDb:
    def test_get_all_etf_codes_excludes_meta(self, client):
        from server.main import get_all_etf_codes
        codes = get_all_etf_codes()
        assert "_comment" not in codes
        assert "STXNDQ" in codes

    def test_get_etf_info_case_insensitive(self, client):
        from server.main import get_etf_info
        info = get_etf_info("stxndq")
        assert info is not None
        assert info["name"] == "Satrix Nasdaq 100 ETF"

    def test_get_etf_info_not_found(self, client):
        from server.main import get_etf_info
        assert get_etf_info("XXXX") is None

    def test_get_etf_holdings(self, client):
        from server.main import get_etf_holdings
        holdings = get_etf_holdings("STXNDQ")
        assert len(holdings) == 3
        assert holdings[0]["ticker"] == "NVDA"

    def test_get_etf_holdings_empty(self, client):
        from server.main import get_etf_holdings
        assert get_etf_holdings("STXESG") == []

    def test_get_etf_holdings_not_found(self, client):
        from server.main import get_etf_holdings
        assert get_etf_holdings("XXXX") == []


# ── CORS ─────────────────────────────────────────────────────────────────────

class TestCors:
    def test_cors_headers_present(self, client):
        resp = client.options("/api/health", headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "GET",
        })
        assert resp.status_code in (200, 204)


# ── Error Handling ───────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_404_for_unknown_api_route(self, client):
        """Unknown API routes return 404 (not caught by SPA fallback)."""
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404

    def test_invalid_json_body(self, client):
        resp = client.post(
            "/api/portfolio/positions",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


# ── Integration: Full Portfolio Lifecycle ────────────────────────────────────

class TestPortfolioLifecycle:
    def test_full_lifecycle(self, client):
        """Test complete portfolio lifecycle: add → view → add more → remove."""
        # 1. Start empty
        resp = client.get("/api/portfolio")
        assert resp.json()["positions"] == []

        # 2. Add first position
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 50.0,
        })
        assert resp.status_code == 200

        # 3. Add second position
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXESG",
            "shares": 200,
            "cost_basis_per_share": 30.0,
        })
        assert resp.status_code == 200

        # 4. Verify both exist
        resp = client.get("/api/portfolio")
        assert len(resp.json()["positions"]) == 2

        # 5. Add more to first position (should average cost)
        resp = client.post("/api/portfolio/positions", json={
            "etf_ticker": "STXNDQ",
            "shares": 100,
            "cost_basis_per_share": 60.0,
        })
        assert resp.json()["shares"] == 200
        assert resp.json()["cost_basis_per_share"] == 55.0

        # 6. Remove second position
        resp = client.delete("/api/portfolio/positions/STXESG")
        assert resp.status_code == 200

        # 7. Verify only one remains
        resp = client.get("/api/portfolio")
        assert len(resp.json()["positions"]) == 1
        assert resp.json()["positions"][0]["etf_ticker"] == "STXNDQ"

        # 8. Remove last position
        resp = client.delete("/api/portfolio/positions/STXNDQ")
        assert resp.status_code == 200

        # 9. Verify empty
        resp = client.get("/api/portfolio")
        assert resp.json()["positions"] == []


# ── Storage backend (file vs KV) ─────────────────────────────────────────────

class TestStorage:
    def test_file_backend_when_kv_not_configured(self, tmp_path, monkeypatch):
        """With no KV env vars, read/write_blob use the file path."""
        from server import storage
        for var in ("KV_REST_API_URL", "KV_REST_API_TOKEN",
                    "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
            monkeypatch.delenv(var, raising=False)
        assert storage.kv_configured() is False
        fp = tmp_path / "blob.json"
        assert storage.read_blob("k", fp) is None
        storage.write_blob("k", {"a": 1}, fp)
        assert fp.exists()
        assert storage.read_blob("k", fp) == {"a": 1}

    def test_kv_backend_when_configured(self, tmp_path, monkeypatch):
        """With KV env vars set, read/write_blob use KV and never touch the file."""
        from server import storage
        monkeypatch.setenv("KV_REST_API_URL", "https://kv.example.com")
        monkeypatch.setenv("KV_REST_API_TOKEN", "tok")
        assert storage.kv_configured() is True

        store = {}
        with patch.object(storage, "_kv_set", lambda key, value: store.__setitem__(key, value)) as _s, \
             patch.object(storage, "_kv_get", lambda key: store.get(key)):
            fp = tmp_path / "should_not_be_written.json"
            storage.write_blob("etf_portfolio", {"positions": []}, fp)
            assert storage.read_blob("etf_portfolio", fp) == {"positions": []}
            assert not fp.exists()   # KV used, file untouched

    def test_kv_read_failure_returns_none(self, tmp_path, monkeypatch):
        """A KV REST failure degrades to None rather than raising."""
        from server import storage
        monkeypatch.setenv("KV_REST_API_URL", "https://kv.example.com")
        monkeypatch.setenv("KV_REST_API_TOKEN", "tok")
        def boom(key):
            raise RuntimeError("network down")
        with patch.object(storage, "_kv_get", boom):
            assert storage.read_blob("etf_portfolio", tmp_path / "x.json") is None
