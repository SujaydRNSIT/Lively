"""
SmartDialer — Campaign Runner (Feature C).

Orchestrates a single outbound campaign:
  1. Pacing engine recommends how many calls to launch.
  2. Safety controller authorises (possibly fewer).
  3. Authorised calls are simulated against the mock provider.
  4. Results are written back to the store and exposed as a snapshot.

All I/O goes through AbstractCampaignStore, so the runner itself is
storage-agnostic.  Calls are simulated (no real SIP trunk) — demo safe.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from typing import Any, Dict, List, Optional

from app.core.dialer.store import (
    AbstractCampaignStore,
    CampaignSnapshot,
    DialerLead,
    MemoryCampaignStore,
)
from app.core.dialer.pacing import pacing_engine
from app.core.dialer.safety import SafetyController

logger = logging.getLogger("lively.core.dialer.campaign")


# --------------------------------------------------------------------------- #
# Mock provider — simulated call outcomes                                       #
# --------------------------------------------------------------------------- #

class MockProvider:
    """
    Simulates a telecom provider.  No real network calls are made.
    Connect probabilities and outcome distributions match typical B2B dial lists.
    """

    CONNECT_PROBABILITY = 0.42    # ~42% answer rate (industry midpoint)
    OUTCOME_WEIGHTS     = {       # distribution of answered-call outcomes
        "answered_ai":    0.55,   # AI agent handles it
        "answered_human": 0.30,   # escalated to human rep
        "no_answer":      0.10,
        "busy":           0.05,
    }

    async def dial(self, lead: DialerLead) -> Dict[str, Any]:
        """Simulate one outbound call.  Returns outcome after realistic delay."""
        delay = random.uniform(1.5, 6.0)   # ring time
        await asyncio.sleep(delay)

        if random.random() < self.CONNECT_PROBABILITY:
            outcomes = list(self.OUTCOME_WEIGHTS.keys())
            weights  = list(self.OUTCOME_WEIGHTS.values())
            outcome  = random.choices(outcomes, weights=weights, k=1)[0]
            return {"status": outcome, "duration": random.uniform(30, 300)}

        return {"status": "no_answer", "duration": 0.0}


_mock_provider = MockProvider()


# --------------------------------------------------------------------------- #
# Campaign Runner                                                               #
# --------------------------------------------------------------------------- #

class CampaignRunner:
    """
    Manages multiple campaigns.  Each campaign has its own SafetyController
    so metrics do not bleed across campaigns.
    """

    def __init__(self, store: AbstractCampaignStore) -> None:
        self._store            = store
        self._safety:          Dict[str, SafetyController] = {}
        self._active_tasks:    Dict[str, asyncio.Task] = {}   # campaign_id → tick task
        self._dial_tasks:      Dict[str, List[asyncio.Task]] = {}  # campaign_id → dial tasks

    # ------------------------------------------------------------------ public

    def create_campaign(
        self,
        name: str,
        leads_data: List[Dict[str, Any]],
        ai_slots: int = 3,
    ) -> str:
        campaign_id = f"cmp_{uuid.uuid4().hex[:10]}"
        leads = [
            DialerLead(
                name    = ld.get("name", f"Lead {i+1}"),
                phone   = ld.get("phone", f"+1555000{i:04d}"),
                company = ld.get("company", ""),
            )
            for i, ld in enumerate(leads_data)
        ]
        self._store.create_campaign(campaign_id, name, leads, ai_slots)
        self._safety[campaign_id] = SafetyController()
        logger.info(f"[Campaign] created {campaign_id} with {len(leads)} leads, {ai_slots} AI slots")
        return campaign_id

    def start(self, campaign_id: str) -> None:
        meta = self._store.get_campaign_meta(campaign_id)
        if not meta:
            raise ValueError(f"Campaign {campaign_id} not found")
        if meta["state"] == "running":
            return
        self._store.update_campaign_meta(campaign_id, state="running")
        task = asyncio.create_task(self._tick_loop(campaign_id))
        self._active_tasks[campaign_id] = task
        logger.info(f"[Campaign] started {campaign_id}")

    def pause(self, campaign_id: str) -> None:
        self._store.update_campaign_meta(campaign_id, state="paused")
        task = self._active_tasks.pop(campaign_id, None)
        if task:
            task.cancel()
        logger.info(f"[Campaign] paused {campaign_id}")

    def snapshot(self, campaign_id: str) -> Optional[CampaignSnapshot]:
        meta  = self._store.get_campaign_meta(campaign_id)
        leads = self._store.get_leads(campaign_id)
        if not meta:
            return None

        counts: Dict[str, int] = {s: 0 for s in
                                   ["queued", "dialing", "answered_ai", "answered_human",
                                    "no_answer", "busy", "dropped", "completed"]}
        for lead in leads:
            counts[lead.status] = counts.get(lead.status, 0) + 1

        safety = self._safety.get(campaign_id)
        last   = safety.latest_decision() if safety else {}

        return CampaignSnapshot(
            campaign_id     = campaign_id,
            name            = meta["name"],
            state           = meta["state"],
            total_leads     = len(leads),
            queued          = counts["queued"],
            dialing         = counts["dialing"],
            answered_ai     = counts["answered_ai"],
            answered_human  = counts["answered_human"],
            no_answer       = counts["no_answer"],
            dropped         = counts["dropped"],
            completed       = counts.get("completed", 0),
            connect_rate    = meta.get("connect_rate", 0.42),
            proposed_dials  = last.get("proposed", 0) if last else meta.get("proposed_dials", 0),
            authorised_dials= last.get("authorised", 0) if last else meta.get("authorised_dials", 0),
            abandon_rate    = last.get("abandon_rate", 0.0) if last else 0.0,
            ai_slots_used   = meta.get("ai_slots_used", 0),
            ai_slots_total  = meta.get("ai_slots_total", 3),
            leads           = [l.to_dict() for l in leads[:50]],   # UI cap
            safety_paused   = meta.get("safety_paused", False),
            circuit_breaker = last.get("circuit_breaker", "closed") if last else "closed",
            created_at      = meta["created_at"],
            updated_at      = meta["updated_at"],
        )

    def list_campaigns(self) -> List[Dict[str, Any]]:
        snapshots = []
        for cid in self._store.list_campaign_ids():
            snap = self.snapshot(cid)
            if snap:
                snapshots.append(snap.to_dict())
        return snapshots

    # ----------------------------------------------------------------- private

    async def _tick_loop(self, campaign_id: str) -> None:
        """Scheduling tick: runs every 5 s while campaign is active."""
        try:
            while True:
                meta = self._store.get_campaign_meta(campaign_id)
                if not meta or meta["state"] != "running":
                    break

                queued_leads = [
                    l for l in self._store.get_leads(campaign_id)
                    if l.status == "queued"
                ]
                if not queued_leads:
                    self._store.update_campaign_meta(campaign_id, state="completed")
                    logger.info(f"[Campaign] {campaign_id} completed (all leads exhausted)")
                    break

                # Count active dials
                dialing_now = sum(
                    1 for l in self._store.get_leads(campaign_id)
                    if l.status == "dialing"
                )
                ai_slots_total = meta.get("ai_slots_total", 3)
                ai_slots_used  = meta.get("ai_slots_used", 0)
                free_slots     = max(0, ai_slots_total - ai_slots_used + 3)  # +3 human estimate

                # Pacing recommendation
                connect_rate = meta.get("connect_rate", 0.42)
                rec = pacing_engine.recommend(
                    connect_rate          = connect_rate,
                    available_agent_slots = free_slots,
                )

                # Safety authorisation
                safety = self._safety[campaign_id]
                dec    = safety.authorise(rec.proposed_dials, free_slots)
                to_dial = max(0, dec.authorised - dialing_now)

                self._store.update_campaign_meta(
                    campaign_id,
                    proposed_dials   = dec.proposed,
                    authorised_dials = dec.authorised,
                    safety_paused    = dec.authorised == 0,
                )

                # Launch up to `to_dial` leads
                batch = queued_leads[:to_dial]
                for lead in batch:
                    lead.status      = "dialing"
                    lead.attempt    += 1
                    lead.dial_started = time.time()
                    self._store.update_lead(campaign_id, lead)
                    task = asyncio.create_task(self._handle_call(campaign_id, lead))
                    self._dial_tasks.setdefault(campaign_id, []).append(task)

                logger.debug(
                    f"[Campaign] {campaign_id} tick: proposed={dec.proposed} "
                    f"authorised={dec.authorised} launching={len(batch)}"
                )
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[Campaign] tick loop error for {campaign_id}: {e}", exc_info=True)

    async def _handle_call(self, campaign_id: str, lead: DialerLead) -> None:
        """Simulate one call and write the outcome back to the store."""
        try:
            meta = self._store.get_campaign_meta(campaign_id)
            if not meta:
                return

            result = await _mock_provider.dial(lead)
            status = result["status"]

            lead.status      = status
            lead.answered_at = time.time() if "answered" in status else None
            lead.ended_at    = time.time()
            lead.handler     = ("ai" if status == "answered_ai" else
                                "human" if status == "answered_human" else None)

            # Update AI slot usage
            if status == "answered_ai":
                self._store.update_campaign_meta(
                    campaign_id,
                    ai_slots_used = max(0, meta.get("ai_slots_used", 0) + 1)
                )

            self._store.update_lead(campaign_id, lead)

            # Rolling connect rate update (exponential moving average)
            connected  = "answered" in status
            old_rate   = meta.get("connect_rate", 0.42)
            new_rate   = 0.9 * old_rate + 0.1 * (1.0 if connected else 0.0)
            abandoned  = status == "dropped"
            self._store.update_campaign_meta(campaign_id, connect_rate=round(new_rate, 4))

            safety = self._safety[campaign_id]
            safety.record_outcome(
                answered       = connected,
                abandoned      = abandoned,
                provider_failed= False,
            )

            # Release AI slot when call ends
            if lead.handler == "ai":
                current_meta = self._store.get_campaign_meta(campaign_id) or {}
                self._store.update_campaign_meta(
                    campaign_id,
                    ai_slots_used = max(0, current_meta.get("ai_slots_used", 1) - 1)
                )

            logger.debug(f"[Campaign] {lead.id} → {status}")
        except Exception as e:
            logger.error(f"[Campaign] _handle_call error: {e}", exc_info=True)
            lead.status  = "dropped"
            lead.ended_at = time.time()
            self._store.update_lead(campaign_id, lead)


# --------------------------------------------------------------------------- #
# Module-level singleton                                                        #
# --------------------------------------------------------------------------- #

_store   = MemoryCampaignStore()
campaign_runner = CampaignRunner(_store)
