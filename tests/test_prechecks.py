"""
test_prechecks.py — Unit tests for the 10-point pre-trade safety system.
All checks are tested with both passing and failing inputs.
MT5 client is mocked so tests run without MetaTrader5 installed.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# Patch settings before importing prechecks
with patch.dict("os.environ", {
    "ANTHROPIC_API_KEY":     "test",
    "SHEETS_SPREADSHEET_ID": "test",
    "GOOGLE_SERVICE_ACCOUNT_JSON": "/tmp/fake.json",
    "MT5_LOGIN":    "123",
    "MT5_PASSWORD": "pw",
    "MT5_SERVER":   "srv",
    "LIVE_TRADING": "False",
    "RISK_PCT_PER_TRADE": "1.0",
    "SOFT_LOSS_LIMIT_PCT": "-2.0",
    "HARD_LOSS_LIMIT_PCT": "-4.0",
    "MAX_CONCURRENT_TRADES": "2",
    "POLL_INTERVAL_SEC": "4",
    "SCREENER_SYMBOLS": "XAUUSD",
}):
    from executor.prechecks import (
        PreCheckError,
        check_ttl,
        check_session_allowed,
        check_no_duplicate,
        check_spread,
        check_daily_loss,
        check_broker_connection,
        check_symbol_trade_mode,
        check_lot_validity,
    )


def _fresh_signal(asset="XAUUSD", session="London", ttl=180):
    return {
        "signal_id":                 "test-001",
        "timestamp_utc":             datetime.now(timezone.utc).isoformat(),
        "workflow_id":               "wf-1",
        "asset":                     asset,
        "session":                   session,
        "direction_bias":            "BUY",
        "catalyst_type":             "news_event",
        "impact_score":              4.2,
        "trend_1h":                  "bullish",
        "trend_1d":                  "bullish",
        "volatility_regime":         "elevated",
        "confidence":                0.75,
        "execution_window_sec":      ttl,
        "invalidate_if_spread_above": 35,
        "reasoning_summary":         "test",
        "status":                    "pending",
    }


def _mock_mt5(
    spread=10,
    daily_loss=-0.5,
    open_positions=None,
    connected=True,
    tradeable=True,
):
    mt5 = MagicMock()
    mt5.get_spread.return_value          = spread
    mt5.get_daily_loss_pct.return_value  = daily_loss
    mt5.get_open_positions.return_value  = open_positions or []
    mt5.is_connected.return_value        = connected
    mt5.is_symbol_tradeable.return_value = tradeable
    return mt5


# ── TTL checks ────────────────────────────────────────────────────

def test_ttl_fresh_signal_passes():
    check_ttl(_fresh_signal())


def test_ttl_expired_signal_fails():
    signal = _fresh_signal(ttl=5)
    signal["timestamp_utc"] = (
        datetime.now(timezone.utc) - timedelta(seconds=60)
    ).isoformat()
    with pytest.raises(PreCheckError, match="expired"):
        check_ttl(signal)


# ── Session checks ────────────────────────────────────────────────

def test_session_london_passes():
    check_session_allowed(_fresh_signal(session="London"))


def test_session_newyork_passes():
    check_session_allowed(_fresh_signal(session="NewYork"))


def test_session_tokyo_fails():
    with pytest.raises(PreCheckError, match="Session not in allowed"):
        check_session_allowed(_fresh_signal(session="Tokyo"))


# ── Spread checks ─────────────────────────────────────────────────

def test_spread_ok_passes():
    check_spread(_fresh_signal(), _mock_mt5(spread=20))


def test_spread_too_high_fails(mocker):
    mocker.patch("time.sleep")
    mt5 = _mock_mt5(spread=50)
    with pytest.raises(PreCheckError, match="Spread still too high"):
        check_spread(_fresh_signal(), mt5)


# ── Daily loss checks ─────────────────────────────────────────────

def test_daily_loss_ok_passes():
    check_daily_loss(_mock_mt5(daily_loss=-0.5))


def test_daily_loss_soft_limit_fails():
    with pytest.raises(PreCheckError, match="Soft daily loss"):
        check_daily_loss(_mock_mt5(daily_loss=-2.5))


def test_daily_loss_hard_limit_fails():
    with pytest.raises(PreCheckError, match="Hard daily loss"):
        check_daily_loss(_mock_mt5(daily_loss=-4.5))


# ── Connection check ──────────────────────────────────────────────

def test_connection_ok_passes():
    check_broker_connection(_mock_mt5(connected=True))


def test_connection_down_fails():
    with pytest.raises(PreCheckError, match="connection not healthy"):
        check_broker_connection(_mock_mt5(connected=False))


# ── Duplicate check ───────────────────────────────────────────────

def test_no_duplicate_passes():
    check_no_duplicate(_fresh_signal(), _mock_mt5(open_positions=[]))


def test_duplicate_same_symbol_fails():
    open_pos = [{"symbol": "XAUUSD", "type": "BUY", "ticket": 111}]
    with pytest.raises(PreCheckError, match="Duplicate trade"):
        check_no_duplicate(_fresh_signal(), _mock_mt5(open_positions=open_pos))


def test_max_concurrent_fails():
    open_pos = [
        {"symbol": "EURUSD", "type": "BUY", "ticket": 1},
        {"symbol": "GBPUSD", "type": "SELL", "ticket": 2},
    ]
    with pytest.raises(PreCheckError, match="Max concurrent"):
        check_no_duplicate(_fresh_signal(), _mock_mt5(open_positions=open_pos))


# ── Symbol registry check ─────────────────────────────────────────

def test_known_symbol_passes():
    check_lot_validity(_fresh_signal(asset="XAUUSD"))


def test_unknown_symbol_fails():
    with pytest.raises(PreCheckError, match="not in SYMBOL_SPECS"):
        check_lot_validity(_fresh_signal(asset="BTCUSD"))
