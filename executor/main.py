"""
main.py — Local execution engine entry point.
Integrates AI signals with the local Macro Risk Engine for Gold (XAUUSD).
"""
import argparse
import json
import logging
import sys
import time

# Top-level imports (These files exist in C:\Users\Administrator\AGENT_423\local\)
import macro_risk_engine 
import agent4_risk
from config import settings

# Package-relative imports (These files exist inside the 'executor' folder)
from . import ai_client, mt5_client, prechecks, sizing
from .monitor import run as monitor_run
from .poller import mark_executed, mark_failed, poll_forever
from .state_machine import TradeFSM, TradeState
from .logger import append_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/executor.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)

def run_trade_cycle(signal: dict) -> None:
    fsm = TradeFSM()
    fsm.signal = signal
    asset = signal["asset"]
    log.info(f"[MAIN] ── New trade cycle ── signal_id={signal['signal_id']} asset={asset}")

    fsm.transition(TradeState.SIGNAL_RECEIVED)

    # 1. Prechecks (Balance, Spread, MT5 Connection)
    fsm.transition(TradeState.PRECHECKING)
    try:
        prechecks.run_all(signal, mt5_client)
    except Exception as e:
        log.warning(f"[MAIN] Pre-check failed: {e}")
        fsm.fail(str(e))
        mark_failed(signal)
        return

    # 2. AI Decision Payload
    fsm.transition(TradeState.AWAITING_AI)
    try:
        ai_payload = _build_ai_payload(signal)
        ai_response = ai_client.get_decision(ai_payload)
        fsm.ai_decision = ai_response
    except Exception as e:
        log.error(f"[MAIN] AI client error: {e}")
        fsm.fail(str(e))
        return

    if ai_response["decision"] == "HOLD":
        log.info(f"[MAIN] AI says HOLD — reason: {ai_response['reason']}")
        fsm.transition(TradeState.IDLE, "AI HOLD")
        mark_executed(signal)
        return

    # 3. MACRO BIAS CIRCUIT BREAKER
    # Map 'BUY' to 'LONG' so the engine understands the logic
    direction_raw = ai_response.get("direction", signal["direction_bias"]).upper()
    direction_map = {"BUY": "LONG", "SELL": "SHORT"}
    mapped_dir = direction_map.get(direction_raw, "NEUTRAL")

    macro_data = macro_risk_engine.get_macro_status()
    macro_bias = macro_data.get("recommended_bias", "NEUTRAL")

    log.info(f"[MACRO] Current Bias: {macro_bias} | Signal Direction: {direction_raw}")

    # Block if Macro says SHORT_ONLY but Signal says BUY
    if macro_bias != "NEUTRAL" and macro_bias != f"{mapped_dir}_ONLY":
        reason = f"Macro Mismatch: Engine says {macro_bias} but signal is {direction_raw}"
        log.warning(f"[MAIN] BLOCKING TRADE: {reason}")
        fsm.transition(TradeState.IDLE, "MACRO_BLOCK")
        mark_executed(signal)
        _log_to_sheets(signal, "BLOCK_MACRO", status="blocked", close_reason=reason)
        return

    # 4. Execution
    fsm.transition(TradeState.EXECUTING)
    try:
        direction = direction_raw.lower()
        balance = mt5_client.get_account_balance()
        atr = mt5_client.get_atr(asset, "H1")
        entry_price = mt5_client.get_current_price(asset, direction)
        sl_price = sizing.compute_sl_price(asset, entry_price, direction, atr)
        tp_price = sizing.compute_tp_price(entry_price, sl_price, direction, rr_ratio=2.0)
        
        lot = sizing.compute_lot_size(
            asset, balance, settings.RISK_PCT_PER_TRADE,
            stop_distance_points=abs(entry_price - sl_price) / _get_point_value(asset)
        )
        
        ticket = mt5_client.place_order(asset, direction, lot, sl_price, tp_price)
        agent4_risk.record_trade_execution()
        mark_executed(signal)
        _log_to_sheets(signal, f"EXECUTE_{direction_raw}", status="executed", ticket=ticket, lot_size=lot)

    except Exception as e:
        log.error(f"[MAIN] Execution error: {e}")
        fsm.fail(str(e))
        mark_failed(signal)
        return

    # 5. Monitoring & Closing
    fsm.transition(TradeState.MONITORING)
    result = monitor_run(ticket, signal, sl_price, tp_price)
    _log_to_sheets(signal, "CLOSED", status="done", pnl_outcome=result.get("pnl_r", 0.0))
    fsm.transition(TradeState.DONE)

def _build_ai_payload(signal: dict) -> dict:
    return {
        "asset": signal["asset"],
        "impact_score": signal["impact_score"],
        "confidence": signal["confidence"],
        "direction_bias": signal["direction_bias"]
    }

def _get_point_value(asset: str) -> float:
    import MetaTrader5 as mt5
    info = mt5.symbol_info(asset)
    return info.point if info else 0.00001

def _log_to_sheets(signal, action, status, pnl_outcome=None, ticket=None, lot_size=None, close_reason=""):
    try:
        append_log(
            signal_id=signal["signal_id"],
            asset=signal["asset"],
            action_taken=action,
            execution_status=status,
            pnl_outcome=pnl_outcome,
            ticket=ticket,
            lot_size=lot_size,
            close_reason=close_reason
        )
    except Exception as e:
        log.error(f"Sheets log failed: {e}")

def main_loop() -> None:
    log.info(f"[MAIN] Starting executor — LIVE_TRADING={settings.LIVE_TRADING}")
    if not mt5_client.connect():
        sys.exit(1)
    for signal in poll_forever():
        run_trade_cycle(signal)

if __name__ == "__main__":
    main_loop()
