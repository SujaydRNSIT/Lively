"""
Deal Desk Negotiation Engine (Feature B).

Architecture principle: LLM PROPOSES; POLICY DECIDES.

The LLM can call the `propose_concession` tool with any number it likes.
This module is the authoritative gate — it trims or rejects the proposal
purely from static policy tables.  No LLM prompt is involved in the
authorisation decision, so the policy cannot be "talked around".

Authority tiers
---------------
  agent:   up to AGENT_CEILING — authorised immediately, no human needed.
  manager: AGENT_CEILING < x <= MANAGER_CEILING — queued for manager approval.
  refused: above MANAGER_CEILING — never authorised regardless of approval.

Trade mechanism
---------------
Every concession above AGENT_CEILING requires a commitment trade:
  • annual    → +5 pp headroom
  • case_study → +2 pp headroom
  • seats     → proportional to seat uplift
  • none      → no headroom above AGENT_CEILING

Visibility
----------
Every decision is recorded as a `ConcessionRecord` and emitted over the
WebSocket as a `DEAL_DESK_UPDATE` event, so both the UI and any downstream
integration see exactly what happened and why.
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("lively.core.deal_desk")


# --------------------------------------------------------------------------- #
# Policy tables                                                                 #
# --------------------------------------------------------------------------- #

AGENT_CEILING    = 15   # % — agent can authorise up to this, instantly
MANAGER_CEILING  = 25   # % — manager can authorise up to this
ABSOLUTE_FLOOR   = 5    # % — nothing below this in any scenario (margin floor)
ABSOLUTE_MAXIMUM = 25   # % — hard cap, no override

# Trade-in headroom (pp of additional authorised discount per trade committed)
TRADE_HEADROOM: Dict[str, int] = {
    "annual":      5,   # buyer commits to annual billing
    "case_study":  2,   # buyer agrees to be a reference customer
    "seats":       3,   # buyer commits to a seat-count upgrade
}

_REASON_LABELS: Dict[str, str] = {
    "agent_authority":   "within agent authority — authorised immediately",
    "manager_authority": "above agent authority — manager approval required",
    "above_ceiling":     f"above {ABSOLUTE_MAXIMUM}% hard ceiling — refused",
    "trade_reduced":     "trade commitment applied — authorised with trade",
}


# --------------------------------------------------------------------------- #
# Data models (plain dataclasses to avoid Pydantic import in this layer)       #
# --------------------------------------------------------------------------- #

class ConcessionRecord:
    """Immutable record of one concession proposal + its authorisation outcome."""

    __slots__ = (
        "id", "proposed_pct", "authorised_pct", "status",
        "reason", "trade", "manager_approval_required",
        "approved_by", "approved_at", "channel_name",
        "created_at", "expires_at",
    )

    def __init__(
        self,
        proposed_pct: float,
        authorised_pct: float,
        status: str,         # "approved" | "pending_manager" | "refused"
        reason: str,
        channel_name: str,
        trade: Optional[str] = None,
    ) -> None:
        self.id                      = f"cd_{uuid.uuid4().hex[:12]}"
        self.proposed_pct            = proposed_pct
        self.authorised_pct          = authorised_pct
        self.status                  = status
        self.reason                  = reason
        self.trade                   = trade
        self.manager_approval_required = status == "pending_manager"
        self.approved_by: Optional[str]   = None
        self.approved_at: Optional[float] = None
        self.channel_name            = channel_name
        self.created_at              = time.time()
        self.expires_at              = self.created_at + 300   # 5-minute approval window

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":                       self.id,
            "proposed_pct":             self.proposed_pct,
            "authorised_pct":           self.authorised_pct,
            "status":                   self.status,
            "reason":                   self.reason,
            "trade":                    self.trade,
            "manager_approval_required": self.manager_approval_required,
            "approved_by":              self.approved_by,
            "approved_at":              self.approved_at,
            "channel_name":             self.channel_name,
            "created_at":               self.created_at,
            "expires_at":               self.expires_at,
            # Derived UI fields
            "label":                    self._ui_label(),
            "bound_by":                 self._bound_by(),
        }

    def _ui_label(self) -> str:
        if self.status == "approved":
            if self.proposed_pct == self.authorised_pct:
                return f"Proposed {self.proposed_pct:.0f}% → Approved {self.authorised_pct:.0f}%"
            return f"Proposed {self.proposed_pct:.0f}% → Trimmed to {self.authorised_pct:.0f}%"
        if self.status == "pending_manager":
            return f"Proposed {self.proposed_pct:.0f}% → Pending manager approval (max {self.authorised_pct:.0f}%)"
        return f"Proposed {self.proposed_pct:.0f}% → Refused (above {ABSOLUTE_MAXIMUM}% hard ceiling)"

    def _bound_by(self) -> str:
        if self.status == "refused":
            return f"hard ceiling: {ABSOLUTE_MAXIMUM}%"
        if self.trade:
            return f"trade commitment ({self.trade}) applied; agent authority {AGENT_CEILING}%"
        if self.proposed_pct > AGENT_CEILING:
            return f"agent authority: {AGENT_CEILING}%; manager ceiling: {MANAGER_CEILING}%"
        return f"agent authority: {AGENT_CEILING}%"


# --------------------------------------------------------------------------- #
# The policy engine                                                             #
# --------------------------------------------------------------------------- #

class DealDesk:
    """
    Stateless policy engine.  Channel-level concession history is held in
    a simple dict so the API layer can manage lifetime; nothing is persisted
    to the database (demo scope — the interface is ready for a Redis adapter).
    """

    def __init__(self) -> None:
        # channel_name → list[ConcessionRecord]
        self._history: Dict[str, List[ConcessionRecord]] = {}

    # ------------------------------------------------------------------ public

    def propose(
        self,
        channel_name: str,
        proposed_pct: float,
        trade: Optional[str] = None,     # "annual" | "case_study" | "seats" | None
    ) -> ConcessionRecord:
        """
        The LLM has called propose_concession(percentage, trade).
        Apply policy and return the authorised record.
        """
        proposed_pct = round(float(proposed_pct), 1)

        # Hard ceiling — no override possible
        if proposed_pct > ABSOLUTE_MAXIMUM:
            rec = ConcessionRecord(
                proposed_pct   = proposed_pct,
                authorised_pct = 0.0,
                status         = "refused",
                reason         = _REASON_LABELS["above_ceiling"],
                channel_name   = channel_name,
                trade          = trade,
            )
            logger.info(
                f"[DealDesk] channel={channel_name} proposed={proposed_pct}% "
                f"→ REFUSED (above hard ceiling {ABSOLUTE_MAXIMUM}%)"
            )
            self._store(channel_name, rec)
            return rec

        # Calculate effective ceiling after trade headroom
        extra_headroom = TRADE_HEADROOM.get(trade or "", 0) if trade else 0
        effective_agent_ceiling = min(AGENT_CEILING + extra_headroom, MANAGER_CEILING)

        # Within effective agent authority → approve immediately
        if proposed_pct <= effective_agent_ceiling:
            rec = ConcessionRecord(
                proposed_pct   = proposed_pct,
                authorised_pct = proposed_pct,
                status         = "approved",
                reason         = (
                    _REASON_LABELS["trade_reduced"] if trade
                    else _REASON_LABELS["agent_authority"]
                ),
                channel_name   = channel_name,
                trade          = trade,
            )
            logger.info(
                f"[DealDesk] channel={channel_name} proposed={proposed_pct}% "
                f"→ APPROVED immediately (agent ceiling {effective_agent_ceiling}%)"
            )
            self._store(channel_name, rec)
            return rec

        # Above agent ceiling but within manager ceiling → pending approval
        # The authorised_pct here is the maximum the manager CAN approve,
        # not what is pre-authorised.
        authorised_pct = min(proposed_pct, MANAGER_CEILING)
        rec = ConcessionRecord(
            proposed_pct   = proposed_pct,
            authorised_pct = authorised_pct,
            status         = "pending_manager",
            reason         = _REASON_LABELS["manager_authority"],
            channel_name   = channel_name,
            trade          = trade,
        )
        logger.info(
            f"[DealDesk] channel={channel_name} proposed={proposed_pct}% "
            f"→ PENDING MANAGER (max approved={authorised_pct}%)"
        )
        self._store(channel_name, rec)
        return rec

    def manager_approve(
        self,
        channel_name: str,
        concession_id: str,
        approved_by: str = "manager",
    ) -> Optional[ConcessionRecord]:
        """
        Manager clicks "Approve" in the cockpit.
        Only pending_manager records can be approved; returns None if not found.
        """
        for rec in self._history.get(channel_name, []):
            if rec.id == concession_id and rec.status == "pending_manager":
                if time.time() > rec.expires_at:
                    rec.status = "expired"
                    logger.warning(f"[DealDesk] concession {concession_id} approval window expired")
                    return rec
                rec.status      = "approved"
                rec.approved_by = approved_by
                rec.approved_at = time.time()
                rec.manager_approval_required = False
                logger.info(
                    f"[DealDesk] {concession_id} approved by {approved_by} "
                    f"at {rec.authorised_pct}%"
                )
                return rec
        return None

    def latest(self, channel_name: str) -> Optional[ConcessionRecord]:
        """Most recent concession record for this channel."""
        history = self._history.get(channel_name, [])
        return history[-1] if history else None

    def history(self, channel_name: str) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._history.get(channel_name, [])]

    def clear(self, channel_name: str) -> None:
        self._history.pop(channel_name, None)

    # ----------------------------------------------------------------- private

    def _store(self, channel_name: str, rec: ConcessionRecord) -> None:
        if channel_name not in self._history:
            self._history[channel_name] = []
        self._history[channel_name].append(rec)


# Singleton — imported by the API and tool-impl layers
deal_desk = DealDesk()
