"""
state_machine.py — Trade lifecycle state machine.
All state transitions are explicit and validated. Illegal transitions raise AssertionError.
This makes debugging and logging trivial.
"""
import logging
from enum import Enum, auto
from typing import Optional

log = logging.getLogger(__name__)


class TradeState(Enum):
    IDLE            = auto()   # Waiting for next signal
    SIGNAL_RECEIVED = auto()   # Signal pulled from queue
    PRECHECKING     = auto()   # Running 10-point safety checks
    AWAITING_AI     = auto()   # Prompt sent to Claude, waiting for response
    EXECUTING       = auto()   # MT5 order being placed
    MONITORING      = auto()   # Position is live, active management running
    CLOSING         = auto()   # Close order being placed
    DONE            = auto()   # Trade complete, ready to return to IDLE
    FAILED          = auto()   # Any unrecoverable error


# Valid transitions from each state
_ALLOWED: dict[TradeState, list[TradeState]] = {
    TradeState.IDLE:            [TradeState.SIGNAL_RECEIVED],
    TradeState.SIGNAL_RECEIVED: [TradeState.PRECHECKING, TradeState.FAILED],
    TradeState.PRECHECKING:     [TradeState.AWAITING_AI, TradeState.IDLE, TradeState.FAILED],
    TradeState.AWAITING_AI:     [TradeState.EXECUTING, TradeState.IDLE, TradeState.FAILED],
    TradeState.EXECUTING:       [TradeState.MONITORING, TradeState.FAILED],
    TradeState.MONITORING:      [TradeState.CLOSING, TradeState.FAILED],
    TradeState.CLOSING:         [TradeState.DONE, TradeState.FAILED],
    TradeState.DONE:            [TradeState.IDLE],
    TradeState.FAILED:          [TradeState.IDLE],
}


class TradeFSM:
    """
    Single-trade finite state machine.
    One instance per trade cycle. Reset to IDLE between trades.
    """

    def __init__(self):
        self.state: TradeState      = TradeState.IDLE
        self.signal: Optional[dict] = None          # Raw signal payload
        self.ai_decision: Optional[dict] = None     # Claude response
        self.order_ticket: Optional[int] = None     # MT5 order ticket
        self.sl_price: Optional[float] = None
        self.tp_price: Optional[float] = None
        self.lot_size: Optional[float] = None
        self.error: Optional[str] = None            # Last error message if FAILED

    def transition(self, new_state: TradeState, reason: str = "") -> None:
        allowed = _ALLOWED[self.state]
        if new_state not in allowed:
            msg = f"Invalid transition: {self.state.name} → {new_state.name}"
            log.error(msg)
            raise AssertionError(msg)
        log.info(f"[FSM] {self.state.name} → {new_state.name}" + (f" | {reason}" if reason else ""))
        self.state = new_state

    def fail(self, reason: str) -> None:
        self.error = reason
        log.error(f"[FSM] FAIL from {self.state.name}: {reason}")
        self.state = TradeState.FAILED

    def reset(self) -> None:
        """Return to IDLE for the next cycle."""
        self.__init__()

    @property
    def signal_id(self) -> str:
        return (self.signal or {}).get("signal_id", "unknown")
