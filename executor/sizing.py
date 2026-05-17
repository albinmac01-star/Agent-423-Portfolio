"""
sizing.py — Dynamic position sizing.
Risk is defined in money, not by lot intuition.
Lot sizes are normalized to symbol min/max/step constraints.
"""
import logging
import math

from config.symbol_specs import SYMBOL_SPECS

log = logging.getLogger(__name__)


def compute_lot_size(
    asset: str,
    account_balance: float,
    risk_pct: float,
    stop_distance_points: float,
) -> float:
    """
    Compute lot size based on account risk percentage and stop distance.

    Args:
        asset:                 Symbol name, must exist in SYMBOL_SPECS.
        account_balance:       Current account equity in account currency.
        risk_pct:              Percentage of balance to risk (e.g. 1.0 = 1%).
        stop_distance_points:  Distance from entry to SL in points.

    Returns:
        Lot size normalized to broker constraints.

    Raises:
        ValueError: If asset not in registry or stop_distance_points is zero.
    """
    if asset not in SYMBOL_SPECS:
        raise ValueError(f"Symbol '{asset}' not in SYMBOL_SPECS. Add it before sizing.")

    if stop_distance_points <= 0:
        raise ValueError(f"stop_distance_points must be > 0, got {stop_distance_points}")

    spec = SYMBOL_SPECS[asset]
    allowed_risk_money  = account_balance * (risk_pct / 100.0)
    point_value_per_lot = spec["point_value_per_lot"]

    raw_lot  = allowed_risk_money / (stop_distance_points * point_value_per_lot)
    lot_step = spec["lot_step"]
    min_lot  = spec["min_lot"]
    max_lot  = spec["max_lot"]

    # Normalize: round DOWN to nearest lot step
    normalized = math.floor(raw_lot / lot_step) * lot_step
    normalized = round(normalized, 10)  # floating-point safety

    # Clamp to min/max
    lot = max(min_lot, min(max_lot, normalized))

    log.info(
        f"[SIZING] {asset} | balance={account_balance:.2f} risk={risk_pct}% "
        f"stop={stop_distance_points}pts | raw={raw_lot:.4f} → lot={lot}"
    )
    return lot


def compute_sl_price(
    asset: str,
    entry_price: float,
    direction: str,
    atr_value: float,
) -> float:
    """
    Compute stop loss price using ATR multiple from SYMBOL_SPECS.

    Args:
        asset:       Symbol name.
        entry_price: Fill price.
        direction:   "BUY" or "SELL".
        atr_value:   Current ATR value in price terms.

    Returns:
        SL price.
    """
    spec     = SYMBOL_SPECS[asset]
    sl_dist  = atr_value * spec["sl_atr_mult"]

    if direction == "BUY":
        sl_price = entry_price - sl_dist
    elif direction == "SELL":
        sl_price = entry_price + sl_dist
    else:
        raise ValueError(f"Invalid direction: {direction}")

    log.info(f"[SIZING] SL={sl_price:.5f} (entry={entry_price:.5f} ± ATR*{spec['sl_atr_mult']}={sl_dist:.5f})")
    return sl_price


def compute_tp_price(
    entry_price: float,
    sl_price: float,
    direction: str,
    rr_ratio: float = 2.0,
) -> float:
    """
    Compute take profit price using a fixed risk-reward ratio.

    Args:
        entry_price: Fill price.
        sl_price:    Stop loss price.
        direction:   "BUY" or "SELL".
        rr_ratio:    Target reward-to-risk ratio (default 2.0 = 2R).

    Returns:
        TP price.
    """
    risk_dist = abs(entry_price - sl_price)
    if direction == "BUY":
        tp_price = entry_price + (risk_dist * rr_ratio)
    elif direction == "SELL":
        tp_price = entry_price - (risk_dist * rr_ratio)
    else:
        raise ValueError(f"Invalid direction: {direction}")

    log.info(f"[SIZING] TP={tp_price:.5f} (RR={rr_ratio})")
    return tp_price
