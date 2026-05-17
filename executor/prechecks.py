"""
prechecks.py — 10-point pre-trade safety gate.
Run ALL checks before placing any order, in dry-run or live mode.
Raises PreCheckError on first failure; caller catches and transitions FSM to FAILED.
"""
import logging
import time
from datetime import datetime, timezone

from config import settings
from config.symbol_specs import SYMBOL_SPECS

log = logging.getLogger(__name__)


class PreCheckError(Exception):
    """Raised when any pre-trade check fails."""
    pass


def run_all(signal: dict, mt5) -> None:
    """
    Run all 10 pre-trade safety checks in order.
    mt5 is the mt5_client module (passed in to allow mocking in tests).
    """
    check_ttl(signal)
    check_session_allowed(signal)
    check_no_duplicate(signal, mt5)
    check_spread(signal, mt5)
    check_daily_loss(mt5)
    check_broker_connection(mt5)
    check_symbol_trade_mode(signal, mt5)
    check_lot_validity(signal)
    check_sl_tp_valid(signal)
    check_slippage_cap(signal)
    log.info(f"[PRECHECKS] All 10 checks passed for {signal['asset']}")


# ── Check 1 — Signal TTL ──────────────────────────────────────────
def check_ttl(signal: dict) -> None:
    ts = datetime.fromisoformat(signal["timestamp_utc"].replace("Z", "+00:00"))
    age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
    ttl = signal["execution_window_sec"]
    if age_sec > ttl:
        raise PreCheckError(
            f"Signal expired: age={age_sec:.0f}s > TTL={ttl}s (signal_id={signal['signal_id']})"
        )
    log.debug(f"[CHECK 1] TTL OK — age={age_sec:.0f}s / TTL={ttl}s")


# ── Check 2 — Session Allowed ─────────────────────────────────────
def check_session_allowed(signal: dict) -> None:
    allowed_sessions = ["London", "NewYork"]
    session = signal.get("session", "")
    if session not in allowed_sessions:
        raise PreCheckError(
            f"Session not in allowed trading sessions: {session}. Allowed: {allowed_sessions}"
        )
    log.debug(f"[CHECK 2] Session OK — {session}")


# ── Check 3 — No Duplicate Open Trade ────────────────────────────
def check_no_duplicate(signal: dict, mt5) -> None:
    asset = signal["asset"]
    open_positions = mt5.get_open_positions()
    for pos in open_positions:
        if pos["symbol"] == asset:
            raise PreCheckError(f"Duplicate trade: position already open for {asset}")

    # Correlation basket check
    spec = SYMBOL_SPECS.get(asset, {})
    basket = spec.get("corr_basket")
    if basket:
        from config.symbol_specs import CORRELATED_BASKETS
        basket_symbols = CORRELATED_BASKETS.get(basket, [])
        for pos in open_positions:
            if pos["symbol"] in basket_symbols:
                raise PreCheckError(
                    f"Correlation basket conflict: {pos['symbol']} already open in basket '{basket}'"
                )

    total_open = len(open_positions)
    if total_open >= settings.MAX_CONCURRENT_TRADES:
        raise PreCheckError(
            f"Max concurrent trades reached: {total_open}/{settings.MAX_CONCURRENT_TRADES}"
        )
    log.debug(f"[CHECK 3] No duplicate — open positions: {total_open}")


# ── Check 4 — Spread Gate ─────────────────────────────────────────
def check_spread(signal: dict, mt5) -> None:
    asset = signal["asset"]
    max_spread = signal.get("invalidate_if_spread_above",
                            SYMBOL_SPECS.get(asset, {}).get("max_spread", 50))

    spread = mt5.get_spread(asset)
    if spread <= max_spread:
        log.debug(f"[CHECK 4] Spread OK — {spread} <= {max_spread}")
        return

    log.warning(f"[CHECK 4] Spread too high: {spread} > {max_spread}. Waiting 30s and retrying...")
    time.sleep(30)
    spread = mt5.get_spread(asset)
    if spread > max_spread:
        raise PreCheckError(f"Spread still too high after recheck: {spread} > {max_spread}")
    log.debug(f"[CHECK 4] Spread OK after recheck — {spread}")


# ── Check 5 — Daily Loss Limit ────────────────────────────────────
def check_daily_loss(mt5) -> None:
    loss_pct = mt5.get_daily_loss_pct()
    if loss_pct <= settings.HARD_LOSS_LIMIT_PCT:
        raise PreCheckError(
            f"Hard daily loss limit hit: {loss_pct:.2f}% <= {settings.HARD_LOSS_LIMIT_PCT}%. "
            "System disabled until next trading day."
        )
    if loss_pct <= settings.SOFT_LOSS_LIMIT_PCT:
        # Soft limit: allow only if confidence is very high (caller responsibility)
        log.warning(f"[CHECK 5] Soft loss limit: {loss_pct:.2f}% — proceed with caution")
        raise PreCheckError(
            f"Soft daily loss limit hit: {loss_pct:.2f}%. No new trades until reviewed."
        )
    log.debug(f"[CHECK 5] Daily loss OK — {loss_pct:.2f}%")


# ── Check 6 — Broker Connection ───────────────────────────────────
def check_broker_connection(mt5) -> None:
    if not mt5.is_connected():
        raise PreCheckError("Broker connection not healthy. MT5 not initialized or disconnected.")
    log.debug("[CHECK 6] Broker connection OK")


# ── Check 7 — Symbol Trade Mode ───────────────────────────────────
def check_symbol_trade_mode(signal: dict, mt5) -> None:
    asset = signal["asset"]
    if not mt5.is_symbol_tradeable(asset):
        raise PreCheckError(f"Symbol {asset} is not tradeable (trade mode disabled or not visible)")
    log.debug(f"[CHECK 7] Symbol trade mode OK — {asset}")


# ── Check 8 — Lot Size Valid ──────────────────────────────────────
def check_lot_validity(signal: dict) -> None:
    asset = signal["asset"]
    if asset not in SYMBOL_SPECS:
        raise PreCheckError(f"Symbol {asset} not in SYMBOL_SPECS registry. Add it before trading.")
    log.debug(f"[CHECK 8] Symbol in registry OK — {asset}")


# ── Check 9 — SL and TP Fields Valid ──────────────────────────────
def check_sl_tp_valid(signal: dict) -> None:
    # SL/TP prices are computed by executor, not signal. This checks that
    # the signal has the data needed to compute them (ATR multiplier available).
    asset = signal["asset"]
    spec = SYMBOL_SPECS.get(asset, {})
    if "sl_atr_mult" not in spec:
        raise PreCheckError(f"sl_atr_mult missing from SYMBOL_SPECS for {asset}")
    log.debug(f"[CHECK 9] SL/TP config OK — sl_atr_mult={spec['sl_atr_mult']}")


# ── Check 10 — Slippage / Deviation Cap Valid ─────────────────────
def check_slippage_cap(signal: dict) -> None:
    # Deviation cap is set in mt5_client. This is a static validation that
    # the value is sensible (not 0, not absurdly large).
    from executor.mt5_client import DEVIATION_CAP
    if not (1 <= DEVIATION_CAP <= 100):
        raise PreCheckError(f"Invalid deviation cap: {DEVIATION_CAP}. Must be between 1 and 100.")
    log.debug(f"[CHECK 10] Slippage cap OK — deviation={DEVIATION_CAP}")
