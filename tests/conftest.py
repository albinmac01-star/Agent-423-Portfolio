"""
conftest.py — Shared pytest fixtures for the local executor test suite.
Patches environment variables and provides reusable signal/MT5 mock factories.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# ── Auto-patch environment for all tests ─────────────────────────

@pytest.fixture(autouse=True)
def patch_env(monkeypatch):
    """Inject safe test environment variables before any module loads settings."""
    env = {
        "ANTHROPIC_API_KEY":              "test-key",
        "CLAUDE_MODEL":                   "claude-sonnet-4-5",
        "SHEETS_SPREADSHEET_ID":          "fake-sheet-id",
        "GOOGLE_SERVICE_ACCOUNT_JSON":    "/tmp/fake_sa.json",
        "MT5_LOGIN":                      "123456",
        "MT5_PASSWORD":                   "testpwd",
        "MT5_SERVER":                     "Demo-Server",
        "LIVE_TRADING":                   "False",
        "RISK_PCT_PER_TRADE":             "1.0",
        "SOFT_LOSS_LIMIT_PCT":            "-2.0",
        "HARD_LOSS_LIMIT_PCT":            "-4.0",
        "MAX_CONCURRENT_TRADES":          "2",
        "POLL_INTERVAL_SEC":              "4",
        "QUEUE_PROVIDER":                 "supabase",
        "SUPABASE_URL":                   "https://test.supabase.co",
        "SUPABASE_KEY":                   "test-key",
        "SUPABASE_TABLE":                 "signals",
        "SCREENER_SYMBOLS":               "XAUUSD,EURUSD",
        "SCREENER_ANOMALY_THRESHOLD_MULT":"2.0",
        "SCREENER_COOLDOWN_SEC":          "1800",
        "SCREENER_POLL_SEC":              "5",
        "SCREENER_ATR_PERIOD":            "14",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)


# ── Signal factory ────────────────────────────────────────────────

@pytest.fixture
def fresh_signal():
    """Return a valid, non-expired TradeSignal dict."""
    def _make(asset="XAUUSD", session="London", ttl=180, direction="BUY",
              trend_1h="bullish", trend_1d="bullish"):
        return {
            "signal_id":                  "test-signal-001",
            "timestamp_utc":              datetime.now(timezone.utc).isoformat(),
            "workflow_id":                "wf-test",
            "asset":                      asset,
            "session":                    session,
            "direction_bias":             direction,
            "catalyst_type":              "test_catalyst",
            "impact_score":               4.2,
            "trend_1h":                   trend_1h,
            "trend_1d":                   trend_1d,
            "volatility_regime":          "elevated",
            "confidence":                 0.75,
            "execution_window_sec":       ttl,
            "invalidate_if_spread_above": 35,
            "investigator_notes":         "test notes",
            "reasoning_summary":          "test reasoning",
            "status":                     "pending",
        }
    return _make


# ── MT5 mock factory ──────────────────────────────────────────────

@pytest.fixture
def mock_mt5():
    """Return a configurable MT5 client mock."""
    def _make(spread=10, daily_loss=-0.5, open_positions=None,
              connected=True, tradeable=True, balance=10_000.0, atr=0.0015):
        mt5 = MagicMock()
        mt5.get_spread.return_value          = spread
        mt5.get_daily_loss_pct.return_value  = daily_loss
        mt5.get_open_positions.return_value  = open_positions or []
        mt5.is_connected.return_value        = connected
        mt5.is_symbol_tradeable.return_value = tradeable
        mt5.get_account_balance.return_value = balance
        mt5.get_atr.return_value             = atr
        mt5.get_current_price.return_value   = 2000.0
        mt5.place_order.return_value         = 999_999_999
        mt5.close_position.return_value      = True
        return mt5
    return _make


# ── Claude response mocks ─────────────────────────────────────────

@pytest.fixture
def execute_response():
    return {
        "decision":    "EXECUTE",
        "direction":   "BUY",
        "confidence":  0.78,
        "reason":      "Macro catalyst aligns with bullish 1H and 1D trend during London.",
        "ttl_seconds": 120,
    }


@pytest.fixture
def hold_response():
    return {
        "decision":    "HOLD",
        "confidence":  0.45,
        "reason":      "Trend conflict between 1H and 1D. Insufficient conviction.",
        "ttl_seconds": 60,
    }
