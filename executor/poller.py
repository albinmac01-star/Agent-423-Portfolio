"""
poller.py — Queue polling loop.
Polls the queue every POLL_INTERVAL_SEC seconds and yields valid pending signals.
Supports Supabase Postgres and AWS SQS via QUEUE_PROVIDER env var.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Generator, Optional

from config import settings
from schemas import validate_signal
import agent4_risk  # Agent 4 injected here

log = logging.getLogger(__name__)


# ── Supabase client ───────────────────────────────────────────────

def _get_supabase():
    from supabase import create_client
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


# ── SQS client ────────────────────────────────────────────────────

def _get_sqs():
    import boto3
    return boto3.client("sqs", region_name=settings.AWS_REGION)


# ── Poll functions ────────────────────────────────────────────────

def _poll_supabase() -> list[dict]:
    """Fetch all pending signals from Supabase, claim them atomically."""
    sb = _get_supabase()
    response = (
        sb.table(settings.SUPABASE_TABLE)
        .select("*")
        .eq("status", "pending")
        .order("timestamp_utc")
        .limit(5)
        .execute()
    )
    signals = response.data or []

    for signal in signals:
        sb.table(settings.SUPABASE_TABLE).update(
            {"status": "claimed"}
        ).eq("signal_id", signal["signal_id"]).execute()
        log.info(f"[POLLER] Claimed signal_id={signal['signal_id']} from Supabase")

    return signals


def _poll_sqs() -> list[dict]:
    """Fetch up to 5 messages from AWS SQS."""
    import json
    sqs = _get_sqs()
    response = sqs.receive_message(
        QueueUrl=settings.SQS_QUEUE_URL,
        MaxNumberOfMessages=5,
        WaitTimeSeconds=5,
        VisibilityTimeout=60,
    )
    messages = response.get("Messages", [])
    signals = []
    for msg in messages:
        try:
            body = json.loads(msg["Body"])
            body["_sqs_receipt"] = msg["ReceiptHandle"]
            signals.append(body)
        except Exception as e:
            log.warning(f"[POLLER] Failed to parse SQS message: {e}")
    return signals


def _delete_sqs(receipt_handle: str) -> None:
    sqs = _get_sqs()
    sqs.delete_message(
        QueueUrl=settings.SQS_QUEUE_URL,
        ReceiptHandle=receipt_handle,
    )


# ── TTL filter ────────────────────────────────────────────────────

def _is_expired(signal: dict) -> bool:
    ts  = datetime.fromisoformat(signal["timestamp_utc"].replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    return age > signal.get("execution_window_sec", 180)


# ── Market Hours ──────────────────────────────────────────────────

def is_market_open() -> bool:
    """
    Checks if the global FX/Gold market is open.
    Closes: Friday 21:00 UTC
    Opens: Sunday 21:00 UTC
    """
    now = datetime.now(timezone.utc)
    
    # Saturday (5) is completely closed
    if now.weekday() == 5:
        return False
        
    # Friday (4) after 21:00 UTC is closed
    if now.weekday() == 4 and now.hour >= 21:
        return False
        
    # Sunday (6) before 21:00 UTC is closed
    if now.weekday() == 6 and now.hour < 21:
        return False
        
    return True


# ── Main poll generator ───────────────────────────────────────────

def poll_forever() -> Generator[dict, None, None]:
    """
    Infinite generator that yields one valid, non-expired signal at a time.
    """
    log.info(f"[POLLER] Starting — provider={settings.QUEUE_PROVIDER} interval={settings.POLL_INTERVAL_SEC}s")

    while True:
        # --- WEEKEND SLEEP CYCLE ---
        if not is_market_open():
            log.info("[POLLER] Market is closed for the weekend. Sleeping for 1 hour...")
            time.sleep(3600)  # Sleep for 60 minutes before checking again
            continue
        # ---------------------------

        try:
            if settings.QUEUE_PROVIDER == "supabase":
                signals = _poll_supabase()
            elif settings.QUEUE_PROVIDER == "sqs":
                signals = _poll_sqs()
            else:
                log.error(f"[POLLER] Unknown QUEUE_PROVIDER: {settings.QUEUE_PROVIDER}")
                signals = []

            for signal in signals:
                try:
                    validate_signal(signal)
                except Exception as e:
                    log.warning(f"[POLLER] Invalid signal payload — skipping: {e}")
                    _update_status(signal, "failed")
                    continue

                if _is_expired(signal):
                    log.info(f"[POLLER] Signal expired — signal_id={signal['signal_id']}")
                    _update_status(signal, "expired")
                    continue

                # --- AGENT 4 CIRCUIT BREAKER ---
                if not agent4_risk.can_trade_today():
                    log.warning(f"[POLLER] Daily limit reached. Rejecting signal_id={signal['signal_id']}")
                    _update_status(signal, "rejected_limit")
                    continue
                # -------------------------------

                yield signal

        except Exception as e:
            log.error(f"[POLLER] Poll cycle error: {e}")

        time.sleep(settings.POLL_INTERVAL_SEC)


def _update_status(signal: dict, status: str) -> None:
    """Update signal status in the queue backend."""
    try:
        if settings.QUEUE_PROVIDER == "supabase":
            sb = _get_supabase()
            sb.table(settings.SUPABASE_TABLE).update(
                {"status": status}
            ).eq("signal_id", signal["signal_id"]).execute()
        elif settings.QUEUE_PROVIDER == "sqs":
            receipt = signal.get("_sqs_receipt")
            if receipt and status in ("executed", "failed", "expired", "rejected_limit"):
                _delete_sqs(receipt)   
    except Exception as e:
        log.error(f"[POLLER] Failed to update status={status}: {e}")


def mark_executed(signal: dict) -> None:
    _update_status(signal, "executed")


def mark_failed(signal: dict) -> None:
    _update_status(signal, "failed")
