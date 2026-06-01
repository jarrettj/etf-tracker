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
    def test_price_cache_miss_fetches_from_yfinance(self, client):
        """Test that cache miss triggers yfinance fetch."""
        mock_info = {"regularMarketPrice": 150.0}
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.info = mock_info
            mock_ticker_cls.return_value = mock_ticker

            from server.main import get_price
            price = get_price("STXNDQ")
            assert price == 150.0

    def test_price_cache_hit_returns_cached(self, client):
        """Test that cache hit returns without yfinance call."""
        from server.main import _save_price_cache, get_price
        _save_price_cache({"STXNDQ": {"price": 200.0, "currency": "ZAR", "_cached_at": 9999999999}})

        with patch("yfinance.Ticker") as mock_ticker_cls:
            price = get_price("STXNDQ")
            assert price == 200.0
            mock_ticker_cls.assert_not_called()

    def test_price_jo_ticker(self, client):
        """Test that .JO tickers are used for SA ETFs."""
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.info = {"regularMarketPrice": 50.0}
            mock_ticker_cls.return_value = mock_ticker

            from server.main import get_price
            get_price("STXNDQ")
            mock_ticker_cls.assert_called_with("STXNDQ.JO")

    def test_price_fallback_sources(self, client):
        """Test price fallback: regularMarketPrice → previousClose → navPrice."""
        from server.main import get_price

        # Test previousClose fallback
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.info = {"previousClose": 75.0}
            mock_ticker_cls.return_value = mock_ticker
            price = get_price("TEST")
            assert price == 75.0

        # Test navPrice fallback
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.info = {"navPrice": 60.0}
            mock_ticker_cls.return_value = mock_ticker
            price = get_price("TEST2")
            assert price == 60.0

    def test_price_returns_none_on_error(self, client):
        """Test that price returns None when yfinance fails."""
        with patch("yfinance.Ticker", side_effect=Exception("Network error")):
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
            data="not json",
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
