"""
mt5_client.py — MetaTrader 5 wrapper with retry logic and dry-run support.
All broker interactions go through this module. Never call MetaTrader5 directly elsewhere.
"""
import logging
import time
from typing import Optional

from config import settings

try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    _MT5_AVAILABLE = False
    mt5 = None  # type: ignore

log = logging.getLogger(__name__)

DEVIATION_CAP = 20   # Maximum slippage in points

# ── Connection ────────────────────────────────────────────────────

def connect() -> bool:
    """Initialize and login to MT5. Returns True on success."""
    if not _MT5_AVAILABLE:
        log.warning("[MT5] MetaTrader5 package not installed — running in stub mode")
        return True  # Allow dry-run without MT5 installed

    for attempt in range(settings.MAX_RETRIES + 1):
        if mt5.initialize(
            login=settings.MT5_LOGIN,
            password=settings.MT5_PASSWORD,
            server=settings.MT5_SERVER,
        ):
            log.info(f"[MT5] Connected — {mt5.account_info()}")
            return True
        log.warning(f"[MT5] Connect attempt {attempt + 1} failed: {mt5.last_error()}")
        time.sleep(settings.RETRY_WAIT_SEC)

    log.error("[MT5] Failed to connect after all retries")
    return False


def disconnect() -> None:
    if _MT5_AVAILABLE:
        mt5.shutdown()
    log.info("[MT5] Disconnected")


def is_connected() -> bool:
    if not _MT5_AVAILABLE:
        return True
    info = mt5.account_info()
    return info is not None


# ── Market Data ───────────────────────────────────────────────────

def get_spread(symbol: str) -> float:
    """Return current spread in points."""
    if not _MT5_AVAILABLE:
        return 10.0   # Stub value for paper trading
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return 9999.0
    info = mt5.symbol_info(symbol)
    spread_points = (tick.ask - tick.bid) / info.point
    return spread_points


def get_current_price(symbol: str, direction: str) -> float:
    """Return entry price: ask for BUY, bid for SELL."""
    if not _MT5_AVAILABLE:
        return 1.0   # Stub
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Cannot get tick for {symbol}")
    return tick.ask if direction == "BUY" else tick.bid


def get_atr(symbol: str, timeframe_str: str = "H1", period: int = 14) -> float:
    """Fetch OHLC bars and compute ATR manually (MT5 Python has no built-in ATR)."""
    if not _MT5_AVAILABLE:
        return 0.0015  # Stub

    _TF_MAP = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
        "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    tf = _TF_MAP.get(timeframe_str, mt5.TIMEFRAME_H1)
    bars = mt5.copy_rates_from_pos(symbol, tf, 0, period + 2)
    if bars is None or len(bars) < period + 1:
        return 0.0

    trs = []
    for i in range(1, len(bars)):
        h, l, c_prev = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        trs.append(max(h - l, abs(h - c_prev), abs(l - c_prev)))

    return sum(trs[-period:]) / period


def get_account_balance() -> float:
    """Return current account equity."""
    if not _MT5_AVAILABLE:
        return 10_000.0   # Stub for paper trading
    info = mt5.account_info()
    return info.equity if info else 0.0


def get_daily_loss_pct() -> float:
    """Return today's PnL as a percentage of starting balance. Negative = loss."""
    if not _MT5_AVAILABLE:
        return 0.0
    # Compute from open equity vs balance at start of day
    # Simplified: use (equity - balance) / balance * 100
    info = mt5.account_info()
    if not info:
        return 0.0
    return ((info.equity - info.balance) / info.balance) * 100


# ── Positions ─────────────────────────────────────────────────────

def get_open_positions() -> list[dict]:
    """Return list of open positions as dicts."""
    if not _MT5_AVAILABLE:
        return []
    positions = mt5.positions_get()
    if positions is None:
        return []
    return [
        {
            "ticket":  p.ticket,
            "symbol":  p.symbol,
            "type":    "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume":  p.volume,
            "price":   p.price_open,
            "sl":      p.sl,
            "tp":      p.tp,
            "profit":  p.profit,
        }
        for p in positions
    ]


def get_position(ticket: int) -> Optional[dict]:
    """Return a single position by ticket, or None if closed."""
    for pos in get_open_positions():
        if pos["ticket"] == ticket:
            return pos
    return None


def is_symbol_tradeable(symbol: str) -> bool:
    if not _MT5_AVAILABLE:
        return True
    info = mt5.symbol_info(symbol)
    if info is None:
        return False
    # TRADE_MODE_FULL = 4; any non-zero trade mode is acceptable for this check
    return info.trade_mode != 0 and info.visible


# ── Order Placement ───────────────────────────────────────────────

def place_order(
    asset: str,
    direction: str,
    lot: float,
    sl_price: float,
    tp_price: float,
) -> int:
    """
    Place a market order with hard broker-side SL and TP.
    Returns MT5 order ticket on success.
    Raises RuntimeError after all retries are exhausted.
    """
    if not settings.LIVE_TRADING:
        log.info(
            f"[MT5][DRY-RUN] Would place {direction} {lot} lots {asset} "
            f"SL={sl_price:.5f} TP={tp_price:.5f}"
        )
        return 999_999_999   # Fake ticket for paper mode

    if not _MT5_AVAILABLE:
        raise RuntimeError("MetaTrader5 not installed but LIVE_TRADING=True")

    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    price      = get_current_price(asset, direction)

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       asset,
        "volume":       lot,
        "type":         order_type,
        "price":        price,
        "sl":           sl_price,
        "tp":           tp_price,
        "deviation":    DEVIATION_CAP,
        "magic":        settings.APP_MAGIC_NUMBER,
        "comment":      "ai-trader",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    for attempt in range(settings.MAX_RETRIES + 1):
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"[MT5] Order placed — ticket={result.order} {direction} {lot} {asset}")
            return result.order
        log.warning(
            f"[MT5] Order attempt {attempt + 1} failed: retcode={result.retcode} "
            f"comment={result.comment}"
        )
        time.sleep(settings.RETRY_WAIT_SEC)

    raise RuntimeError(
        f"Order failed after {settings.MAX_RETRIES + 1} attempts for {direction} {asset}"
    )


def close_position(ticket: int, symbol: str) -> bool:
    """Close an open position by ticket. Returns True on success."""
    if not settings.LIVE_TRADING:
        log.info(f"[MT5][DRY-RUN] Would close ticket={ticket} {symbol}")
        return True

    if not _MT5_AVAILABLE:
        return False

    pos = get_position(ticket)
    if not pos:
        log.warning(f"[MT5] close_position: ticket {ticket} not found (may already be closed)")
        return True

    close_type = mt5.ORDER_TYPE_SELL if pos["type"] == "BUY" else mt5.ORDER_TYPE_BUY
    price      = get_current_price(symbol, "SELL" if pos["type"] == "BUY" else "BUY")

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "position":     ticket,
        "symbol":       symbol,
        "volume":       pos["volume"],
        "type":         close_type,
        "price":        price,
        "deviation":    DEVIATION_CAP,
        "magic":        settings.APP_MAGIC_NUMBER,
        "comment":      "ai-trader-close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    for attempt in range(settings.MAX_RETRIES + 1):
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"[MT5] Position closed — ticket={ticket}")
            return True
        log.warning(f"[MT5] Close attempt {attempt + 1} failed: retcode={result.retcode}")
        time.sleep(settings.RETRY_WAIT_SEC)

    log.error(f"[MT5] Failed to close ticket={ticket} after all retries")
    return False
