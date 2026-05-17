"""
logger.py — Outbound Webhook Journaler (Clean PNL Version).
Bypasses local Google credentials by sending MT5 execution data directly to n8n.
"""
import logging
import requests
import datetime
from typing import Optional
from config import settings

log = logging.getLogger(__name__)

# Pull the Webhook URL safely from the hidden .env file
N8N_WEBHOOK_URL = settings.N8N_WEBHOOK_URL

def append_log(
    signal_id: str,
    asset: str,
    action_taken: str,
    execution_status: str,
    pnl_outcome: Optional[float] = None,
    # MT5 Physical Execution Data
    ticket: Optional[int] = None,
    lot_size: Optional[float] = None,
    sl_price: Optional[float] = None,
    tp_price: Optional[float] = None,
    close_reason: str = "",
    **kwargs # Absorbs any old bloated data sent by main.py so it doesn't crash
) -> None:
    """Packages strictly financial execution data and fires POST to n8n."""
    
    payload = {
        "Timestamp": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "Signal ID": signal_id,
        "Asset": asset,
        "Action Taken": action_taken,
        "Execution Status": execution_status,
        "MT5 Ticket": ticket if ticket else "N/A",
        "Lot Size": lot_size if lot_size else "N/A",
        "SL Price": sl_price if sl_price else "N/A",
        "TP Price": tp_price if tp_price else "N/A",
        "Close Reason": close_reason if close_reason else "N/A",
        "Gross PnL": round(pnl_outcome, 2) if pnl_outcome is not None else 0.0
    }
    
    try:
        response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        log.info(f"[LOGGER] Pushed clean PNL log to n8n for {signal_id}")
    except requests.exceptions.RequestException as e:
        log.error(f"[LOGGER] Failed to push log to n8n: {e}")
