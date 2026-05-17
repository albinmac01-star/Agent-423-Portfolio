"""
test_state_machine.py — Unit tests for the TradeState FSM.
Verifies all valid transitions and asserts invalid ones raise AssertionError.
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
    from executor.state_machine import TradeFSM, TradeState


def test_initial_state_is_idle():
    fsm = TradeFSM()
    assert fsm.state == TradeState.IDLE


def test_happy_path_transitions():
    """Full successful trade lifecycle."""
    fsm = TradeFSM()
    path = [
        TradeState.SIGNAL_RECEIVED,
        TradeState.PRECHECKING,
        TradeState.AWAITING_AI,
        TradeState.EXECUTING,
        TradeState.MONITORING,
        TradeState.CLOSING,
        TradeState.DONE,
        TradeState.IDLE,
    ]
    for state in path:
        fsm.transition(state)
        assert fsm.state == state


def test_hold_path():
    """Claude returns HOLD — goes back to IDLE after AWAITING_AI."""
    fsm = TradeFSM()
    fsm.transition(TradeState.SIGNAL_RECEIVED)
    fsm.transition(TradeState.PRECHECKING)
    fsm.transition(TradeState.AWAITING_AI)
    fsm.transition(TradeState.IDLE, reason="Claude HOLD")
    assert fsm.state == TradeState.IDLE


def test_precheck_fail_path():
    """Precheck failure goes directly to FAILED then IDLE."""
    fsm = TradeFSM()
    fsm.transition(TradeState.SIGNAL_RECEIVED)
    fsm.transition(TradeState.PRECHECKING)
    fsm.fail("spread too high")
    assert fsm.state == TradeState.FAILED
    assert fsm.error == "spread too high"
    fsm.transition(TradeState.IDLE)
    assert fsm.state == TradeState.IDLE


def test_invalid_transition_raises():
    """Jumping from IDLE directly to EXECUTING is illegal."""
    fsm = TradeFSM()
    with pytest.raises(AssertionError, match="Invalid transition"):
        fsm.transition(TradeState.EXECUTING)


def test_invalid_forward_skip_raises():
    """Cannot jump from SIGNAL_RECEIVED to MONITORING."""
    fsm = TradeFSM()
    fsm.transition(TradeState.SIGNAL_RECEIVED)
    with pytest.raises(AssertionError, match="Invalid transition"):
        fsm.transition(TradeState.MONITORING)


def test_reset_returns_to_idle():
    fsm = TradeFSM()
    fsm.transition(TradeState.SIGNAL_RECEIVED)
    fsm.signal = {"signal_id": "abc"}
    fsm.reset()
    assert fsm.state == TradeState.IDLE
    assert fsm.signal is None
    assert fsm.order_ticket is None


def test_signal_id_property():
    fsm = TradeFSM()
    assert fsm.signal_id == "unknown"
    fsm.signal = {"signal_id": "sig-42"}
    assert fsm.signal_id == "sig-42"


def test_fail_records_error():
    fsm = TradeFSM()
    fsm.transition(TradeState.SIGNAL_RECEIVED)
    fsm.fail("MT5 disconnected")
    assert fsm.error == "MT5 disconnected"
    assert fsm.state == TradeState.FAILED


def test_double_fail_not_possible():
    """From FAILED you can only go to IDLE, not FAILED again."""
    fsm = TradeFSM()
    fsm.transition(TradeState.SIGNAL_RECEIVED)
    fsm.fail("error")
    with pytest.raises(AssertionError):
        fsm.fail("second error")
