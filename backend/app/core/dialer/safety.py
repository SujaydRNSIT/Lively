"""
SmartDialer — Safety Controller (Feature C).

Architecture principle: PACING PROPOSES; SAFETY AUTHORISES.

The pacing engine produces a recommended dial count.
This class is the authoritative gate — it may reduce (never increase) that
number based on real-time safety metrics.  It mirrors the Deal Desk pattern
so the same "LLM/pacing proposes; policy decides" story is visible at every
level of the architecture.

Safety rules (applied in priority order):
  1. If the circuit breaker is OPEN → authorise 0.
  2. If abandon rate > ABANDON_RATE_THRESHOLD → authorise 0 (pause).
  3. Authorised = min(proposed, HARD_MAX_CONCURRENT).
  4. Authorised = min(authorised, available_slots).

All decisions are logged for the dashboard.
"""
from __future__ import annotations

import time
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("lively.core.dialer.safety")

# --------------------------------------------------------------------------- #
# Policy constants                                                              #
# --------------------------------------------------------------------------- #

HARD_MAX_CONCURRENT    = 20     # absolute upper bound regardless of pacing
ABANDON_RATE_THRESHOLD = 0.05   # >5% abandon rate triggers a pause
CIRCUIT_BREAKER_WINDOW = 60     # seconds: rolling window for failure counting
CIRCUIT_BREAKER_TRIPS  = 3      # provider failures in the window to open circuit
CIRCUIT_HALF_OPEN_SECS = 30     # time before half-open probe


# --------------------------------------------------------------------------- #
# Decision record                                                               #
# --------------------------------------------------------------------------- #

@dataclass
class SafetyDecision:
    proposed:          int
    authorised:        int
    reason:            str
    abandon_rate:      float
    circuit_breaker:   str       # "closed" | "open" | "half_open"
    timestamp:         float     = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposed":        self.proposed,
            "authorised":      self.authorised,
            "reason":          self.reason,
            "abandon_rate":    round(self.abandon_rate, 4),
            "circuit_breaker": self.circuit_breaker,
            "timestamp":       self.timestamp,
            # UI display
            "label":           f"Proposed {self.proposed} → Approved {self.authorised} · {self.reason}",
        }


# --------------------------------------------------------------------------- #
# Safety Controller                                                             #
# --------------------------------------------------------------------------- #

class SafetyController:
    """
    Authorises the number of simultaneous dials proposed by the pacing engine.
    Invariant: authorised <= proposed (always — the controller never increases).
    """

    def __init__(self) -> None:
        self._abandon_window:    Deque[float] = deque()   # timestamps of abandoned calls
        self._total_calls:       int          = 0
        self._circuit_state:     str          = "closed"  # closed | open | half_open
        self._circuit_opened_at: Optional[float] = None
        self._failure_times:     Deque[float] = deque()   # provider failure timestamps
        self._decisions:         List[SafetyDecision] = []

    # ------------------------------------------------------------------ public

    def authorise(self, proposed: int, available_slots: int) -> SafetyDecision:
        """
        Apply safety rules and return the authorised dial count.
        `available_slots` is the number of free agent slots right now.
        """
        cb_state = self._circuit_breaker_state()

        # Rule 1: circuit breaker open
        if cb_state == "open":
            dec = SafetyDecision(
                proposed        = proposed,
                authorised      = 0,
                reason          = "circuit breaker open — provider failures detected",
                abandon_rate    = self._rolling_abandon_rate(),
                circuit_breaker = cb_state,
            )
            self._log(dec)
            return dec

        # Rule 2: abandon rate exceeded
        ar = self._rolling_abandon_rate()
        if ar > ABANDON_RATE_THRESHOLD:
            dec = SafetyDecision(
                proposed        = proposed,
                authorised      = 0,
                reason          = f"abandon rate {ar:.1%} > {ABANDON_RATE_THRESHOLD:.0%} threshold — paused",
                abandon_rate    = ar,
                circuit_breaker = cb_state,
            )
            self._log(dec)
            return dec

        # Rule 3 + 4: cap to hard max and available slots
        authorised = min(proposed, HARD_MAX_CONCURRENT, available_slots)
        reason_parts = []
        if authorised < proposed:
            if authorised == HARD_MAX_CONCURRENT:
                reason_parts.append(f"capped at hard max {HARD_MAX_CONCURRENT}")
            elif authorised == available_slots:
                reason_parts.append(f"capped to {available_slots} available slot(s)")
        else:
            reason_parts.append("within safe limits")

        dec = SafetyDecision(
            proposed        = proposed,
            authorised      = authorised,
            reason          = "; ".join(reason_parts) or "within safe limits",
            abandon_rate    = ar,
            circuit_breaker = cb_state,
        )
        self._log(dec)
        return dec

    def record_outcome(self, answered: bool, abandoned: bool, provider_failed: bool) -> None:
        """Called after each call resolves."""
        now = self._total_calls
        self._total_calls += 1

        if abandoned:
            self._abandon_window.append(time.time())

        if provider_failed:
            self._failure_times.append(time.time())
            # Prune failures outside the window
            cutoff = time.time() - CIRCUIT_BREAKER_WINDOW
            while self._failure_times and self._failure_times[0] < cutoff:
                self._failure_times.popleft()
            if len(self._failure_times) >= CIRCUIT_BREAKER_TRIPS and self._circuit_state == "closed":
                self._circuit_state     = "open"
                self._circuit_opened_at = time.time()
                logger.warning("[SafetyController] Circuit breaker OPENED after provider failures")

    def reset_circuit_breaker(self) -> None:
        """Manual reset (half-open probe succeeded)."""
        self._circuit_state     = "closed"
        self._circuit_opened_at = None
        self._failure_times.clear()
        logger.info("[SafetyController] Circuit breaker reset to CLOSED")

    def latest_decision(self) -> Optional[Dict[str, Any]]:
        return self._decisions[-1].to_dict() if self._decisions else None

    def decision_history(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._decisions[-20:]]

    # ----------------------------------------------------------------- private

    def _rolling_abandon_rate(self) -> float:
        if self._total_calls == 0:
            return 0.0
        cutoff = time.time() - 300   # 5-minute window
        while self._abandon_window and self._abandon_window[0] < cutoff:
            self._abandon_window.popleft()
        return len(self._abandon_window) / max(1, self._total_calls)

    def _circuit_breaker_state(self) -> str:
        if self._circuit_state == "open":
            elapsed = time.time() - (self._circuit_opened_at or 0)
            if elapsed >= CIRCUIT_HALF_OPEN_SECS:
                self._circuit_state = "half_open"
                logger.info("[SafetyController] Circuit breaker → HALF_OPEN (probe allowed)")
                return "half_open"
        return self._circuit_state

    def _log(self, dec: SafetyDecision) -> None:
        self._decisions.append(dec)
        logger.info(
            f"[SafetyController] proposed={dec.proposed} → authorised={dec.authorised} "
            f"[{dec.reason}] abandon={dec.abandon_rate:.1%} cb={dec.circuit_breaker}"
        )
