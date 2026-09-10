"""
SmartDialer — Storage Abstraction Layer (Feature C).

AbstractCampaignStore defines the interface that CampaignRunner uses.
MemoryCampaignStore is the in-process implementation used for the demo.

Replacing it with a Redis or Postgres implementation only requires:
  1. Subclass AbstractCampaignStore.
  2. Pass the new store to CampaignRunner (or swap the singleton in dialer.py).
  No other code needs to change.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- #
# Lead data model                                                               #
# --------------------------------------------------------------------------- #

LEAD_STATUSES = frozenset({"queued", "dialing", "answered_ai", "answered_human", "no_answer", "busy", "dropped", "completed"})


@dataclass
class DialerLead:
    """One prospective contact in the dial queue."""
    id:           str   = field(default_factory=lambda: f"lead_{uuid.uuid4().hex[:10]}")
    name:         str   = "Unknown"
    phone:        str   = ""
    company:      str   = ""
    status:       str   = "queued"          # one of LEAD_STATUSES
    attempt:      int   = 0
    dial_started: Optional[float] = None
    answered_at:  Optional[float] = None
    ended_at:     Optional[float] = None
    handler:      Optional[str]   = None    # "ai" | "human"
    channel_name: Optional[str]   = None    # Lively channel if answered by AI

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}   # type: ignore[attr-defined]


@dataclass
class CampaignSnapshot:
    """Read-only view of a campaign returned by status queries."""
    campaign_id:    str
    name:           str
    state:          str          # "idle" | "running" | "paused" | "completed"
    total_leads:    int
    queued:         int
    dialing:        int
    answered_ai:    int
    answered_human: int
    no_answer:      int
    dropped:        int
    completed:      int

    connect_rate:       float    # rolling connect rate [0,1]
    proposed_dials:     int      # what pacing recommended
    authorised_dials:   int      # what safety controller approved
    abandon_rate:       float    # rolling abandon rate [0,1]
    ai_slots_used:      int
    ai_slots_total:     int

    leads:              List[Dict[str, Any]]
    safety_paused:      bool
    circuit_breaker:    str      # "closed" | "open" | "half_open"

    created_at:  float
    updated_at:  float

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


# --------------------------------------------------------------------------- #
# Abstract store interface                                                      #
# --------------------------------------------------------------------------- #

class AbstractCampaignStore(ABC):
    """Interface for campaign persistence. Swap the concrete class for Redis/PG."""

    @abstractmethod
    def create_campaign(self, campaign_id: str, name: str, leads: List[DialerLead],
                        ai_slots: int) -> None: ...

    @abstractmethod
    def get_leads(self, campaign_id: str) -> List[DialerLead]: ...

    @abstractmethod
    def update_lead(self, campaign_id: str, lead: DialerLead) -> None: ...

    @abstractmethod
    def get_campaign_meta(self, campaign_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def update_campaign_meta(self, campaign_id: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def list_campaign_ids(self) -> List[str]: ...

    @abstractmethod
    def delete_campaign(self, campaign_id: str) -> None: ...


# --------------------------------------------------------------------------- #
# In-memory implementation                                                      #
# --------------------------------------------------------------------------- #

class MemoryCampaignStore(AbstractCampaignStore):
    """Thread-safe (GIL) in-process store for the demo.  Ready to be replaced."""

    def __init__(self) -> None:
        # campaign_id → {"meta": dict, "leads": dict[lead_id, DialerLead]}
        self._data: Dict[str, Dict[str, Any]] = {}

    def create_campaign(self, campaign_id: str, name: str, leads: List[DialerLead],
                        ai_slots: int) -> None:
        self._data[campaign_id] = {
            "meta": {
                "campaign_id":      campaign_id,
                "name":             name,
                "state":            "idle",
                "ai_slots_total":   ai_slots,
                "ai_slots_used":    0,
                "proposed_dials":   0,
                "authorised_dials": 0,
                "connect_rate":     0.42,   # bootstrap estimate
                "abandon_rate":     0.0,
                "safety_paused":    False,
                "circuit_breaker":  "closed",
                "created_at":       time.time(),
                "updated_at":       time.time(),
            },
            "leads": {lead.id: lead for lead in leads},
        }

    def get_leads(self, campaign_id: str) -> List[DialerLead]:
        data = self._data.get(campaign_id)
        return list(data["leads"].values()) if data else []

    def update_lead(self, campaign_id: str, lead: DialerLead) -> None:
        if campaign_id in self._data:
            self._data[campaign_id]["leads"][lead.id] = lead
            self._data[campaign_id]["meta"]["updated_at"] = time.time()

    def get_campaign_meta(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        data = self._data.get(campaign_id)
        return dict(data["meta"]) if data else None

    def update_campaign_meta(self, campaign_id: str, **kwargs: Any) -> None:
        if campaign_id in self._data:
            self._data[campaign_id]["meta"].update(kwargs)
            self._data[campaign_id]["meta"]["updated_at"] = time.time()

    def list_campaign_ids(self) -> List[str]:
        return list(self._data.keys())

    def delete_campaign(self, campaign_id: str) -> None:
        self._data.pop(campaign_id, None)
