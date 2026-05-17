"""
test_sizing.py — Unit tests for dynamic position sizing math.
Tests lot normalization, edge cases, and SL/TP calculations.
"""
import pytest
from unittest.mock import patch

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
    from executor.sizing import compute_lot_size, compute_sl_price, compute_tp_price


# ── Lot size ──────────────────────────────────────────────────────

def test_eurusd_standard_lot():
    """1% risk, 100 point stop, EURUSD: should give reasonable lot"""
    lot = compute_lot_size("EURUSD", account_balance=10_000, risk_pct=1.0, stop_distance_points=100)
    assert 0.01 <= lot <= 10.0
    assert lot == round(lot, 2)


def test_xauusd_small_account():
    lot = compute_lot_size("XAUUSD", account_balance=1_000, risk_pct=1.0, stop_distance_points=150)
    assert lot >= 0.01   # Never below min_lot


def test_nas100_large_stop():
    lot = compute_lot_size("NAS100", account_balance=10_000, risk_pct=1.0, stop_distance_points=500)
    assert lot >= 0.1


def test_lot_clamped_to_max():
    """Very small stop → raw lot could exceed max; must be clamped"""
    lot = compute_lot_size("EURUSD", account_balance=1_000_000, risk_pct=5.0, stop_distance_points=1)
    assert lot <= 10.0


def test_lot_min_clamp():
    """Very large stop and small balance — should return min_lot"""
    lot = compute_lot_size("XAUUSD", account_balance=100, risk_pct=1.0, stop_distance_points=10_000)
    assert lot == 0.01


def test_unknown_symbol_raises():
    with pytest.raises(ValueError, match="not in SYMBOL_SPECS"):
        compute_lot_size("DOGUSD", 10_000, 1.0, 100)


def test_zero_stop_raises():
    with pytest.raises(ValueError, match="must be > 0"):
        compute_lot_size("EURUSD", 10_000, 1.0, 0)


def test_lot_step_normalized():
    """Returned lot must always be a multiple of lot_step"""
    lot = compute_lot_size("EURUSD", account_balance=10_000, risk_pct=1.0, stop_distance_points=75)
    # EURUSD lot_step = 0.01
    assert abs(round(lot / 0.01) * 0.01 - lot) < 1e-9


# ── SL price ─────────────────────────────────────────────────────

def test_buy_sl_below_entry():
    sl = compute_sl_price("XAUUSD", entry_price=2000.0, direction="BUY", atr_value=10.0)
    assert sl < 2000.0


def test_sell_sl_above_entry():
    sl = compute_sl_price("EURUSD", entry_price=1.0800, direction="SELL", atr_value=0.0010)
    assert sl > 1.0800


def test_sl_distance_equals_atr_mult():
    entry = 2000.0
    atr   = 10.0
    sl    = compute_sl_price("XAUUSD", entry, "BUY", atr)
    # XAUUSD sl_atr_mult = 1.2
    expected_dist = atr * 1.2
    assert abs((entry - sl) - expected_dist) < 1e-6


# ── TP price ─────────────────────────────────────────────────────

def test_buy_tp_above_entry():
    sl = 1990.0
    tp = compute_tp_price(entry_price=2000.0, sl_price=sl, direction="BUY", rr_ratio=2.0)
    assert tp > 2000.0


def test_sell_tp_below_entry():
    sl = 1.0850
    tp = compute_tp_price(entry_price=1.0800, sl_price=sl, direction="SELL", rr_ratio=2.0)
    assert tp < 1.0800


def test_rr_ratio_correct():
    entry, sl = 2000.0, 1990.0
    risk = entry - sl
    tp   = compute_tp_price(entry, sl, "BUY", rr_ratio=2.0)
    reward = tp - entry
    assert abs(reward / risk - 2.0) < 1e-6
