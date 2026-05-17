"""
monitor.py — Active position management loop.
Monitors an open trade on a 5-minute cadence.
Only escalates to Claude when a rule-based warning fires — not on every candle.
"""
import logging
import time
from typing import Optional

from config import settings
from config.symbol_specs import SESSIONS
from executor import mt5_client, ai_client

log = logging.getLogger(__name__)

# Monitoring constants
MONITOR_INTERVAL_SEC  = 30     # Check every 30 seconds
ADX_PERIOD            = 14
ADX_DECAY_THRESHOLD   = 20.0   # ADX below this = momentum decaying
ADX_DECAY_BARS        = 3      # Must be below threshold for N consecutive bars
SPREAD_SPIKE_MULT     = 2.5    # Spread > normal * this = spike
SESSION_CLOSE_WARN_MIN = 15    # Warn N minutes before session ends


def run(ticket: int, signal: dict, sl_price: float, tp_price: float) -> dict:
    """
    Monitor an active position until it is closed (by TP, SL, or manager decision).

    Returns a dict with:
        - close_reason: "TP_HIT" | "SL_HIT" | "MANAGER_CLOSE" | "RULE_CLOSE" | "ERROR"
        - pnl_r: final PnL in R-multiples
        - post_trade_label: str for Sheets logging
    """
    asset     = signal["asset"]
    direction = signal["direction_bias"]

    log.info(f"[MONITOR] Watching ticket={ticket} {direction} {asset}")
    _adx_decay_bars = 0
    normal_spread   = mt5_client.get_spread(asset)

    while True:
        time.sleep(MONITOR_INTERVAL_SEC)

        # Is position still open?
        pos = mt5_client.get_position(ticket)
        if pos is None:
            log.info(f"[MONITOR] ticket={ticket} no longer open — closed by broker (TP/SL hit)")
            pnl_r = _estimate_pnl_r(signal, sl_price, direction, outcome="broker_closed")
            return {
                "close_reason":      "TP_OR_SL_HIT",
                "pnl_r":             pnl_r,
                "post_trade_label":  "auto_closed_by_broker",
            }

        unrealized_pnl = pos["profit"]
        spread_now     = mt5_client.get_spread(asset)
        entry_price    = pos["price"]
        current_price  = mt5_client.get_current_price(asset, direction)
        risk_dist      = abs(entry_price - sl_price)
        unrealized_r   = (
            (current_price - entry_price) / risk_dist if direction == "BUY"
            else (entry_price - current_price) / risk_dist
        )

        # ── Rule 1: ADX momentum decay ─────────────────────────
        adx_now = _get_adx(asset)
        if adx_now is not None and adx_now < ADX_DECAY_THRESHOLD:
            _adx_decay_bars += 1
            if _adx_decay_bars >= ADX_DECAY_BARS:
                action = _escalate_to_claude({
                    "event":                "MOMENTUM_DECAY",
                    "asset":               asset,
                    "session":             signal["session"],
                    "adx_now":             adx_now,
                    "adx_threshold":       ADX_DECAY_THRESHOLD,
                    "bars_below_threshold": _adx_decay_bars,
                    "spread_now":          spread_now,
                    "unrealized_r":        round(unrealized_r, 3),
                    "trade_state":         f"open, {unrealized_r:+.2f}R unrealized",
                })
                if action == "CLOSE_POSITION":
                    return _close(ticket, asset, signal, sl_price, direction, "MOMENTUM_DECAY", unrealized_r)
                else:
                    _adx_decay_bars = 0   # Reset after Claude says hold
        else:
            _adx_decay_bars = 0

        # ── Rule 2: Spread spike ────────────────────────────────
        if spread_now > normal_spread * SPREAD_SPIKE_MULT:
            action = _escalate_to_claude({
                "event":       "SPREAD_SPIKE",
                "asset":       asset,
                "session":     signal["session"],
                "spread_now":  spread_now,
                "unrealized_r": round(unrealized_r, 3),
                "trade_state": f"open, {unrealized_r:+.2f}R unrealized",
            })
            if action == "CLOSE_POSITION":
                return _close(ticket, asset, signal, sl_price, direction, "SPREAD_SPIKE", unrealized_r)

        # ── Rule 3: Session ending soon ────────────────────────
        if _session_closing_soon(signal["session"]):
            action = _escalate_to_claude({
                "event":       "SESSION_ENDING",
                "asset":       asset,
                "session":     signal["session"],
                "unrealized_r": round(unrealized_r, 3),
                "trade_state": f"open, {unrealized_r:+.2f}R unrealized",
            })
            if action == "CLOSE_POSITION":
                return _close(ticket, asset, signal, sl_price, direction, "SESSION_ENDING", unrealized_r)

        log.debug(f"[MONITOR] ticket={ticket} unrealized={unrealized_r:+.2f}R spread={spread_now} adx={adx_now}")


# ── Helpers ───────────────────────────────────────────────────────

def _escalate_to_claude(payload: dict) -> str:
    try:
        return ai_client.get_management_decision(payload)
    except Exception as e:
        log.error(f"[MONITOR] Claude escalation failed: {e} — defaulting to HOLD")
        return "HOLD"


def _close(ticket, asset, signal, sl_price, direction, reason, unrealized_r) -> dict:
    log.info(f"[MONITOR] Closing position ticket={ticket} reason={reason}")
    mt5_client.close_position(ticket, asset)
    label = "rule_close" if reason != "MANAGER_CLOSE" else "manager_close"
    return {
        "close_reason":     reason,
        "pnl_r":            round(unrealized_r, 3),
        "post_trade_label": label,
    }


def _get_adx(asset: str) -> Optional[float]:
    """Compute ADX from MT5 H1 bars. Returns None if data unavailable."""
    try:
        import MetaTrader5 as mt5
        bars = mt5.copy_rates_from_pos(asset, mt5.TIMEFRAME_M5, 0, ADX_PERIOD + 5)
        if bars is None or len(bars) < ADX_PERIOD:
            return None
        # Simplified directional movement calculation
        highs  = [b["high"]  for b in bars]
        lows   = [b["low"]   for b in bars]
        closes = [b["close"] for b in bars]
        return _calc_adx(highs, lows, closes, ADX_PERIOD)
    except Exception:
        return None


def _calc_adx(highs, lows, closes, period) -> float:
    """Compute ADX from price arrays."""
    import math
    plus_dm, minus_dm, tr_list = [], [], []
    for i in range(1, len(highs)):
        h_diff = highs[i] - highs[i - 1]
        l_diff = lows[i - 1] - lows[i]
        plus_dm.append(max(h_diff, 0) if h_diff > l_diff else 0)
        minus_dm.append(max(l_diff, 0) if l_diff > h_diff else 0)
        tr_list.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))

    def smooth(lst):
        s = sum(lst[:period])
        out = [s]
        for v in lst[period:]:
            s = s - s / period + v
            out.append(s)
        return out

    atr_s   = smooth(tr_list)[-1]
    pdm_s   = smooth(plus_dm)[-1]
    mdm_s   = smooth(minus_dm)[-1]
    if atr_s == 0:
        return 0.0
    pdi  = 100 * pdm_s / atr_s
    mdi  = 100 * mdm_s / atr_s
    diff = abs(pdi - mdi)
    summ = pdi + mdi
    dx   = 100 * diff / summ if summ != 0 else 0
    return dx


def _session_closing_soon(session_name: str) -> bool:
    """Return True if the current session ends within SESSION_CLOSE_WARN_MIN minutes."""
    import datetime
    session = SESSIONS.get(session_name)
    if not session:
        return False
    now_utc    = datetime.datetime.now(datetime.timezone.utc)
    end_hour   = session["end"]
    session_end = now_utc.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    if session_end < now_utc:
        session_end = session_end.replace(day=session_end.day + 1)
    mins_left = (session_end - now_utc).total_seconds() / 60
    return mins_left <= SESSION_CLOSE_WARN_MIN


def _estimate_pnl_r(signal, sl_price, direction, outcome) -> float:
    """Estimate PnL in R when we don't have exact fill numbers."""
    return 0.0   # Will be updated when Sheets logs the actual MT5 history
