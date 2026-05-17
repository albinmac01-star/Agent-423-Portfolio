"""
agent4_risk.py — The Ultimate Circuit Breaker.
Enforces the absolute rule: 1 trade in a day, always win or loss.
"""
import os
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# The physical location of the memory file on your server
STATE_FILE = "trade_state.json"

def can_trade_today() -> bool:
    """Checks the local state file to see if a trade has already occurred today."""
    if not os.path.exists(STATE_FILE):
        log.info("[AGENT 4] No previous trades found. Cleared to execute.")
        return True
        
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            
        last_trade_date = state.get("last_trade_date")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        if last_trade_date == today:
            log.warning(f"[AGENT 4] LOCKDOWN ACTIVE. Trade already taken today ({today}).")
            return False
            
        log.info("[AGENT 4] New day detected. Cleared to execute.")
        return True
        
    except Exception as e:
        log.error(f"[AGENT 4] State file corrupted: {e}. Defaulting to LOCKDOWN to protect capital.")
        return False

def record_trade_execution():
    """Logs today's date to the state file instantly after MT5 executes a trade."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = {"last_trade_date": today}
    
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
        
    log.info(f"[AGENT 4] Trade recorded. System is now LOCKED for the remainder of {today}.")