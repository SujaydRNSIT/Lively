import re
import json
import time
import logging
from typing import Dict, Any, Optional, List, Tuple

from sqlalchemy import select

from app.config import settings
from app.models.schemas import DealState, ChatTurn, ObjectionRecord, DealStageEnum, ChangeLogEntry
from app.core.decision import decision_engine, REBUTTALS
from app.core.understanding import (
    rule_based_understanding, extract_email, extract_day, extract_time, extract_duration, duration_minutes, OBJECTION_TYPES,
)
from app.core.background import run_blocking, spawn
from app.core.security import rate_limiter
from app.core.tools_impl.calendar import calendar_service
from app.core.tools_impl.crm import crm_service
from app.core.tools_impl.escalation import escalation_service
from app.db.redis_client import redis_client
from app.db.postgres import async_session_factory, DealStateTable
from app.services.email_service import email_service

logger = logging.getLogger("lively.core.deal_state_engine")

DEFAULT_TOPIC = "Lively Real-Time Voice AI Sales Deep-Dive"
DEFAULT_HOST = "Senior Solutions Architect"
_AGENT_SCHEDULING_WORDS = ("schedule", "book", "walkthrough", "meet", "tomorrow", "calendar", "slot", "demo", "available", "open")
_AGENT_ASK_RE = re.compile(
    r"\b(?:how about|would you like to|shall we|does that work|would .{0,40} work|which (?:one |time )?works|want me to (?:book|schedule)"
    r"|should i (?:book|schedule)|do you prefer)\b"
)
_AGENT_CONFIRMED_RE = re.compile(
    r"\b(?:i\s+have|i've|we\s+have|we've)\s+(?:booked|scheduled|reserved|locked\s+in)\s+(?:a|the|our|your)?\s*(?:demo|walkthrough|meeting|appointment|call|session|slot)\b"
    r"|\b(?:demo|walkthrough|meeting)\s+(?:is|has\s+been)\s+(?:locked\s+in|booked|scheduled|confirmed)\b"
    r"|\bcalendar\s+(?:invite|invitation)\s+(?:has\s+been|is)\s+dispatched\b"
)
_BUYER_ASKED_RE = re.compile(
    r"\b(schedule|book|reserve|set\s*up|lock\s*in|walkthrough|demo|meeting|that\s+works|works\s+for\s+me|sounds\s+good|yes\s+please|let'?s\s+do\s+it)\b"
)
_SENTIMENT_SCORES = {"Positive": 0.5, "Enthusiastic": 0.8, "Neutral": 0.0, "Hesitant": -0.3, "Skeptical": -0.4, "Frustrated": -0.7}
_RESOLUTION_LABELS = {
    "accepted": "buyer accepted the answer",
    "moved_on": "buyer moved on",
    "advanced_to_demo": "buyer booked a demo",
    "manual": "marked resolved by the rep",
}


class DealStateEngine:
    """
    Task 6.1, 6.2, 6.3:
    In-memory deal state with Redis cache + Postgres write-through.
    Every buyer turn is turned into an `understanding` (LLM or rules) and merged here: qualification,
    objections (raised, repeated, resolved), availability-checked booking, escalation and CRM activity.
    """
    def __init__(self):
        self._states: Dict[str, DealState] = {}

    # ------------------------------------------------------------ lifecycle
    def get_or_create(self, channel_name: str) -> DealState:
        if channel_name not in self._states:
            state = DealState(
                channel_name=channel_name,
                session_id=f"sess_{channel_name}_{int(time.time())}"
            )
            state.available_slots = calendar_service.next_open_slots(3)
            self._states[channel_name] = state
        return self._states[channel_name]

    def get_state(self, channel_name: str) -> Optional[DealState]:
        return self._states.get(channel_name)

    def reset_state(self, channel_name: str) -> DealState:
        calendar_service.release_channel(channel_name)
        new_state = DealState(
            channel_name=channel_name,
            session_id=f"sess_{channel_name}_{int(time.time())}"
        )
        new_state.available_slots = calendar_service.next_open_slots(3)
        self._states[channel_name] = new_state
        return new_state

    def record_turn(
        self,
        channel_name: str,
        role: str,
        text: str,
        sentiment: str = "Neutral",
        understanding: Optional[Dict[str, Any]] = None
    ) -> DealState:
        state = self.get_or_create(channel_name)
        log_start = len(state.change_log)
        if role == "buyer":
            u = understanding or rule_based_understanding(text)
            state.transcript.append(ChatTurn(role=role, content=text, timestamp=time.time(), sentiment=u.get("sentiment") or sentiment))
            self._apply_understanding(state, text, u)
        else:
            state.transcript.append(ChatTurn(role=role, content=text, timestamp=time.time(), sentiment=sentiment))
            if role == "agent":
                self.check_agent_demo_confirmation(state, text)
        self._finalize(state, log_start)
        return state

    def _finalize(self, state: DealState, log_start: int) -> None:
        self._refresh_qualification(state)
        self._recompute_stage(state)
        state.available_slots = calendar_service.next_open_slots(3, ignore_channel=state.channel_name)
        state.next_best_action = decision_engine.evaluate_next_action(state)
        state.updated_at = time.time()
        for entry in state.change_log[log_start:]:
            crm_service.record_activity(state, entry.field, entry.description)
        crm_service.upsert_from_state(state)
        spawn(self._persist_state, state)

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _log(state: DealState, field: str, old: Any, new: Any, description: str) -> None:
        state.change_log.append(ChangeLogEntry(field=field, old_value=old, new_value=new, description=description))

    @staticmethod
    def _add_action(state: DealState, note: str) -> None:
        if note not in state.action_items:
            state.action_items.append(note)

    @staticmethod
    def _demo_confirmed(state: DealState) -> bool:
        return bool(state.scheduled_demo and state.scheduled_demo.get("status") == "CONFIRMED")

    # Kept for callers and tests that used the old method names
    def _extract_day(self, lower: str, *_args, **_kwargs) -> Optional[str]:
        return extract_day(lower)

    def _extract_time(self, lower: str, *_args, **_kwargs) -> Optional[str]:
        return extract_time(lower)

    def _extract_duration(self, lower: str) -> str:
        return extract_duration(lower)

    # ------------------------------------------------------------ merge
    def _apply_understanding(self, state: DealState, text: str, u: Dict[str, Any]) -> None:
        state.last_understanding = {
            "source": u.get("source"),
            "intent": u.get("intent"),
            "demo_request": u.get("demo_request"),
            "objections": [o.get("type") for o in u.get("objections", [])],
            "wants_human": u.get("wants_human"),
        }
        if u.get("email"):
            self._set_contact_email(state, u["email"])
        if u.get("company") and state.company in ("Prospective Client", "", None):
            self._log(state, "company", state.company, u["company"], f"Company identified: {u['company']}.")
            state.company = u["company"]
            state.crm_lead.company = u["company"]

        self._merge_users(state, u.get("user_count"))
        self._merge_budget(state, u.get("budget"))
        self._merge_authority(state, u.get("role"), u.get("is_decision_maker"))
        self._merge_timeline(state, u.get("timeline"))
        self._merge_needs(state, u.get("pain_points") or [])
        if u.get("competitor"):
            state.competitor_mentioned = u["competitor"]
        self._update_objections(state, text, u)
        if u.get("sentiment"):
            state.sentiment = u["sentiment"]
            state.sentiment_score = _SENTIMENT_SCORES.get(u["sentiment"], 0.0)
        self._handle_scheduling(state, text, text.lower(), u)
        self._refresh_qualification(state)
        self._check_escalation(state, u)

    def _merge_users(self, state: DealState, count: Optional[int]) -> None:
        if not count or count == state.users:
            return
        old = state.users
        state.users = count
        state.bant.need["scale"] = f"{count} seats"
        description = (f"User scale set to {count} seats." if old is None
                       else f"User scale changed from {old} -> {count} seats. Pricing tier re-evaluated.")
        self._log(state, "users", old, count, description)

    def _merge_budget(self, state: DealState, budget: Optional[str]) -> None:
        if not budget:
            return
        value = budget.strip()
        if value.startswith("$") or value[:1].isdigit():
            value = value.upper()
        if value == state.budget:
            return
        old = state.budget
        state.budget = value
        state.bant.budget["status"] = "Identified"
        state.bant.budget["value"] = value
        state.crm_lead.deal_value = value
        self._log(state, "budget", old, value, f"Budget {'set' if old is None else 'updated'} to {value}.")

    def _merge_authority(self, state: DealState, role: Optional[str], decision_maker: Optional[bool]) -> None:
        if role is None and decision_maker is None:
            return
        authority = state.bant.authority
        old_role = authority.get("role")
        if role and role != old_role:
            authority["role"] = role
            state.decision_maker = role
            state.buyer_persona = role
            self._log(state, "authority", old_role, role, f"Authority identified: {role}.")
        if decision_maker is not None and authority.get("decision_maker") != decision_maker:
            authority["decision_maker"] = decision_maker
            if not role:
                self._log(state, "authority", None, decision_maker,
                          "Buyer is the decision maker." if decision_maker else "Buyer is not the final decision maker.")
        authority["status"] = "Identified"

    def _merge_timeline(self, state: DealState, timeline: Optional[str]) -> None:
        if not timeline or timeline == state.timeline:
            return
        old = state.timeline
        state.timeline = timeline
        state.bant.timeline["status"] = "Identified"
        state.bant.timeline["timeframe"] = timeline
        self._log(state, "timeline", old, timeline, f"Timeline {'set' if old is None else 'updated'}: {timeline}.")

    def _merge_needs(self, state: DealState, pain_points: List[str]) -> None:
        pains = state.bant.need.setdefault("pain_points", [])
        known = {p.lower() for p in pains}
        added = [p for p in pain_points if p and p.lower() not in known]
        if not added:
            return
        pains.extend(added)
        del pains[:-5]
        state.needs = list(pains)
        state.bant.need["status"] = "Identified"
        self._log(state, "need", None, added, f"Need identified: {'; '.join(added)}.")

    # ------------------------------------------------------------ objections
    def _sync_objection_lists(self, state: DealState) -> None:
        state.active_objections = [o for o in state.objections if not o.resolved]
        state.resolved_objections = [o for o in state.objections if o.resolved]

    def _resolve(self, state: DealState, record: ObjectionRecord, how: str) -> None:
        record.resolved = True
        record.status = "Resolved"
        record.resolution = how
        self._log(state, "objection", record.type, None,
                  f"{record.type.title()} objection resolved ({_RESOLUTION_LABELS.get(how, how)}).")

    def _update_objections(self, state: DealState, text: str, u: Dict[str, Any]) -> None:
        raised: List[str] = []
        for item in u.get("objections", []):
            obj_type = item.get("type")
            if obj_type in OBJECTION_TYPES and obj_type not in raised:
                raised.append(obj_type)

        # 1. Age open objections: repeated ones stay live, others close when the buyer accepts or moves on.
        for record in [o for o in state.objections if not o.resolved]:
            if record.type in raised:
                record.times_raised += 1
                record.turns_since_raised = 0
                record.utterance = text
            elif u.get("accepts_previous_answer"):
                self._resolve(state, record, "accepted")
            else:
                record.turns_since_raised += 1
                if record.turns_since_raised >= 2:
                    self._resolve(state, record, "moved_on")

        # 2. Open new ones.
        open_types = {o.type for o in state.objections if not o.resolved}
        for obj_type in raised:
            if obj_type in open_types:
                continue
            record = ObjectionRecord(type=obj_type, category=obj_type, utterance=text, suggested_rebuttal=REBUTTALS.get(obj_type))
            record.times_raised = 1 + sum(1 for o in state.objections if o.type == obj_type)
            state.objections.append(record)
            self._log(state, "objection", None, obj_type, f"{obj_type.title()} objection raised: \"{text[:80]}\"")
        self._sync_objection_lists(state)

    def resolve_objection(self, channel_name: str, objection_id: str) -> Optional[DealState]:
        state = self.get_or_create(channel_name)
        log_start = len(state.change_log)
        for record in state.objections:
            if not record.resolved and objection_id in (record.id, record.type, record.category):
                self._resolve(state, record, "manual")
        self._sync_objection_lists(state)
        self._finalize(state, log_start)
        return state

    # ------------------------------------------------------------ contact
    def _set_contact_email(self, state: DealState, email: str) -> None:
        if email == state.contact_email:
            return
        old = state.contact_email
        state.contact_email = email
        state.crm_lead.contact_email = email
        self._log(state, "contact_email", old, email, f"Contact email captured: {email}.")
        demo = state.scheduled_demo
        if self._demo_confirmed(state) and demo.get("email") != email:
            demo["email"] = email
            self._send_invite(state)

    def _resolve_target_email(self, state: DealState, text: str = "") -> Optional[str]:
        spoken = extract_email(text) if text else None
        if spoken:
            return spoken
        if state.contact_email:
            return state.contact_email
        if state.crm_lead.contact_email:
            return state.crm_lead.contact_email
        for turn in reversed(state.transcript):
            if turn.role == "buyer":
                found = extract_email(turn.content)
                if found:
                    return found
        return None  # no default inbox: the agent asks for an email instead

    # ------------------------------------------------------------ scheduling
    def _last_agent_proposal(self, state: DealState) -> Tuple[Optional[Tuple[str, str]], bool]:
        """(day, time) the agent last proposed, and whether the agent was asking about scheduling at all."""
        for turn in reversed(state.transcript):
            if turn.role in ("agent", "assistant"):
                lower = turn.content.lower()
                if not any(w in lower for w in _AGENT_SCHEDULING_WORDS):
                    return None, False
                day, time_str = extract_day(lower), extract_time(lower)
                slot = (day, time_str) if day and time_str else None
                return slot, bool(slot) or bool(_AGENT_ASK_RE.search(lower))
        return None, False

    def _handle_scheduling(self, state: DealState, text: str, lower: str, u: Dict[str, Any]) -> None:
        request = u.get("demo_request")
        confirmed = self._demo_confirmed(state)

        if request == "cancel":
            if confirmed:
                self._cancel_demo(state)
            state.pending_demo_request = False
            state.slot_conflict = None
            return
        if request == "decline":
            self._log(state, "demo_declined", None, None, "Buyer declined to book a demo for now.")
            state.pending_demo_request = False
            state.slot_conflict = None
            return

        proposal, agent_asked = self._last_agent_proposal(state)
        offered = (state.slot_conflict or {}).get("alternatives") or state.available_slots
        day, time_str = extract_day(lower), extract_time(lower)
        requested = (u.get("requested_time_text") or "").lower()
        if requested:
            day = day or extract_day(requested)
            time_str = time_str or extract_time(requested)

        awaiting_time = state.pending_demo_request or bool(state.slot_conflict)
        agreed = request == "accept_proposed" or bool(u.get("agrees_to_proposal"))
        if confirmed and request != "reschedule" and not awaiting_time:
            return  # a confirmed demo only moves on an explicit reschedule or cancel

        slot: Optional[Tuple[str, str]] = None
        choice = u.get("slot_choice")
        if choice is not None and offered and (awaiting_time or agent_asked):
            index = choice if choice >= 0 else len(offered) - 1
            if 0 <= index < len(offered):
                slot = ("label", offered[index])
        if slot is None and day and time_str and (request in ("request", "reschedule") or awaiting_time or agreed):
            slot = (day, time_str)
        if slot is None and agreed and proposal:
            slot = (day or proposal[0], time_str or proposal[1])
        if slot is None:
            if request in ("request", "reschedule") or (agreed and agent_asked):
                if not state.pending_demo_request:
                    self._log(state, "demo_request", None, None, "Buyer wants a demo; offering open slots.")
                state.pending_demo_request = True
            return
        self._book(state, slot, text, lower)

    def _book(self, state: DealState, slot: Tuple[str, str], text: str, lower: str) -> Optional[Dict[str, Any]]:
        duration = extract_duration(lower)
        if slot[0] == "label":
            label = f"{slot[1]} ({duration})"
        else:
            label = f"{slot[0]} at {slot[1]} {settings.CALENDAR_TZ_LABEL} ({duration})"
        check = calendar_service.check_slot(label, duration_minutes(duration), ignore_channel=state.channel_name)
        if not check["ok"]:
            state.slot_conflict = {"requested": label, "reason": check["reason"], "alternatives": check["alternatives"]}
            state.pending_demo_request = True
            self._log(state, "slot_conflict", None, label, f"Requested {label} is unavailable: {check['reason']}.")
            return None
        return self._confirm_booking(state, label, check, duration, text)

    def _confirm_booking(self, state: DealState, label: str, check: Dict[str, Any], duration: str,
                         text: str = "", topic: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        email = email or self._resolve_target_email(state, text)
        if email and not state.contact_email:
            state.contact_email = email
            state.crm_lead.contact_email = email
        old_demo = state.scheduled_demo
        topic = topic or DEFAULT_TOPIC
        booking = calendar_service.reserve(label, check["start_utc"], check["end_utc"], state.channel_name, email, topic)
        prep = email_service.prepare_demo_confirmation(email or "", {
            "time": label,
            "duration": duration,
            "topic": topic,
            "host": DEFAULT_HOST,
            "meeting_link": booking["meeting_link"],
            "meeting_id": booking["meeting_id"],
        })
        demo = {
            "meeting_id": booking["meeting_id"],
            "status": "CONFIRMED",
            "time": label,
            "start_utc": check["start_utc"].isoformat(),
            "email": email,
            "duration": duration,
            "topic": topic,
            "host": DEFAULT_HOST,
            "meeting_link": booking["meeting_link"],
            "google_calendar_link": prep["google_calendar_url"],
            "booked_at": time.time(),
            "invite_status": "queued" if email else "pending_email",
            "message": f"Demo confirmed for {label}." + ("" if email else " Waiting for the buyer's email to send the invite."),
        }
        state.scheduled_demo = demo
        state.pending_demo_request = False
        state.slot_conflict = None
        for record in [o for o in state.objections if not o.resolved]:
            self._resolve(state, record, "advanced_to_demo")
        self._sync_objection_lists(state)

        verb = "rescheduled" if old_demo else "booked"
        self._add_action(state, f"Demo {verb}: {label}" + (f" with {email}" if email else " (need email for invite)"))
        self._log(state, "scheduled_demo", old_demo.get("time") if old_demo else None, label, f"Demo {verb} for {label}.")
        if email:
            self._send_invite(state)
        return demo

    def _send_invite(self, state: DealState) -> None:
        demo = state.scheduled_demo
        email = demo.get("email") if demo else None
        if not email:
            return
        if not rate_limiter.allow(f"email:{state.channel_name}", settings.EMAILS_PER_CHANNEL_PER_HOUR, 3600):
            demo["invite_status"] = "rate_limited"
            logger.warning(f"Invite email rate limit reached for channel {state.channel_name}")
            return
        demo["invite_status"] = "sending"

        def _done(result: Dict[str, Any]) -> None:
            if state.scheduled_demo is demo:
                demo["invite_status"] = "delivered" if (result or {}).get("mode") == "smtp" else "preview_only"
                demo["invite_error"] = (result or {}).get("error")

        # SMTP runs in a worker thread so the voice turn never waits on the mail server.
        run_blocking(email_service.send_demo_confirmation, email, dict(demo), on_result=_done)
        self._add_action(state, f"Invite sent to {email}")

    def _cancel_demo(self, state: DealState) -> None:
        demo = state.scheduled_demo
        calendar_service.release_channel(state.channel_name)
        state.scheduled_demo = None
        self._add_action(state, f"Demo cancelled: {demo['time']}")
        self._log(state, "scheduled_demo", demo["time"], None, f"Demo for {demo['time']} cancelled by the buyer.")

    def book_demo(self, channel_name: str, time_slot: str, email: Optional[str] = None, topic: Optional[str] = None) -> Dict[str, Any]:
        """Direct booking (UI button, REST tool, function call). Same availability rules as voice."""
        state = self.get_or_create(channel_name)
        log_start = len(state.change_log)
        if email in ("", "prospect@example.com"):
            email = None
        lower = (time_slot or "").lower()
        day, time_str, duration = extract_day(lower), extract_time(lower), extract_duration(lower)
        label = f"{day} at {time_str} {settings.CALENDAR_TZ_LABEL} ({duration})" if day and time_str else time_slot
        check = calendar_service.check_slot(label, duration_minutes(duration), ignore_channel=channel_name)
        if not check["ok"]:
            state.slot_conflict = {"requested": label, "reason": check["reason"], "alternatives": check["alternatives"]}
            state.pending_demo_request = True
            self._log(state, "slot_conflict", None, label, f"Requested {label} is unavailable: {check['reason']}.")
            self._finalize(state, log_start)
            return {"status": "UNAVAILABLE", "time": label, "reason": check["reason"], "alternatives": check["alternatives"]}
        demo = self._confirm_booking(state, label, check, duration, topic=topic, email=email)
        self._finalize(state, log_start)
        return demo

    def set_contact(self, channel_name: str, email: str, name: Optional[str] = None, company: Optional[str] = None) -> DealState:
        state = self.get_or_create(channel_name)
        log_start = len(state.change_log)
        if name and name.strip():
            state.contact_name = name.strip()
            state.crm_lead.contact_name = name.strip()
        if company and company.strip():
            state.company = company.strip()
            state.crm_lead.company = company.strip()
        self._set_contact_email(state, email)
        self._finalize(state, log_start)
        return state

    def send_invite(self, channel_name: str, email: str) -> Optional[Dict[str, Any]]:
        """(Re)send the confirmed demo's invite. Returns the demo, or None if nothing is booked."""
        state = self.get_or_create(channel_name)
        if not self._demo_confirmed(state):
            return None
        log_start = len(state.change_log)
        if email != state.contact_email:
            self._set_contact_email(state, email)  # sends to the new address
        else:
            state.scheduled_demo["email"] = email
            self._send_invite(state)
        self._finalize(state, log_start)
        return state.scheduled_demo

    def check_agent_demo_confirmation(self, state: DealState, text: str) -> None:
        """
        If the agent says it booked a demo, make the calendar match, but only when the buyer actually
        asked for or agreed to one and the agent named a concrete day and time.
        """
        if self._demo_confirmed(state):
            return
        lower = text.lower()
        if not _AGENT_CONFIRMED_RE.search(lower):
            return
        buyer_agreed = False
        for turn in reversed(state.transcript):
            if turn.role == "buyer":
                buyer_agreed = bool(_BUYER_ASKED_RE.search(turn.content.lower()))
                break
        if not buyer_agreed:
            logger.info("Agent mentioned a booking the buyer never asked for. Skipping false trigger.")
            return
        day, time_str = extract_day(lower), extract_time(lower)
        if day and time_str:
            self._book(state, (day, time_str), text, lower)

    # ------------------------------------------------------------ qualification & stage
    def _refresh_qualification(self, state: DealState) -> None:
        dimensions = [state.bant.budget, state.bant.authority, state.bant.need, state.bant.timeline]
        known = sum(1 for d in dimensions if d.get("status") == "Identified")
        state.qualification_score = 25 * known
        if known == 4 and not state.lead_qualified:
            state.lead_qualified = True
            state.qualified_at = time.time()
            self._add_action(state, "Lead qualified: budget, authority, need and timeline captured")
            self._log(state, "qualification", False, True, "Lead qualified (budget, authority, need and timeline all captured).")

    def _recompute_stage(self, state: DealState) -> None:
        if state.stage == DealStageEnum.CLOSED and not state.escalation:
            return
        if state.escalation:
            stage = DealStageEnum.ESCALATED
        elif self._demo_confirmed(state) or state.slot_conflict or state.pending_demo_request:
            stage = DealStageEnum.DEMO_SCHEDULING
        elif any(not o.resolved for o in state.objections):
            stage = DealStageEnum.OBJECTION_HANDLING
        elif state.qualification_score >= 50:
            stage = DealStageEnum.QUALIFICATION
        else:
            stage = DealStageEnum.DISCOVERY
        if stage != state.stage:
            self._log(state, "stage", state.stage.value, stage.value, f"Stage moved from {state.stage.value} to {stage.value}.")
            state.stage = stage

    # ------------------------------------------------------------ escalation
    def _check_escalation(self, state: DealState, u: Dict[str, Any]) -> None:
        if state.escalation:
            return
        if u.get("wants_human"):
            self._escalate(state, "Buyer asked to speak with a human.", "Immediate", "buyer_request")
        elif u.get("legal_or_contract"):
            self._escalate(state, "Enterprise legal or contract terms need a human account executive.", "High", "legal_terms")
        elif sum(1 for t in state.transcript if t.role == "buyer" and t.sentiment == "Frustrated") >= 2:
            self._escalate(state, "Buyer frustration repeated across turns.", "High", "frustration")
        else:
            # Three strikes, not two: PS21's own example raises pricing and competitor concerns back to back.
            persistent = sorted({o.type for o in state.objections if o.times_raised >= 3})
            open_count = sum(1 for o in state.objections if not o.resolved)
            if persistent or open_count >= 3:
                detail = ", ".join(persistent) if persistent else f"{open_count} open objections"
                self._escalate(state, f"Objections keep coming back ({detail}).", "Standard", "persistent_objections")

    def _escalate(self, state: DealState, reason: str, urgency: str, trigger: str) -> Dict[str, Any]:
        record = escalation_service.build_handoff(state.channel_name, reason, urgency, state, trigger)
        state.escalation = {k: record[k] for k in ("id", "reason", "urgency", "trigger", "status", "bridge_url", "created_at",
                                                    "summary", "recent_turns", "transcript_count")}
        self._add_action(state, f"Escalated to a human AE: {reason}")
        self._log(state, "escalation", None, trigger, f"Handed off to a human AE ({urgency}): {reason}")
        return state.escalation

    def escalate(self, channel_name: str, reason: str, urgency: str = "Immediate", trigger: str = "manual") -> Dict[str, Any]:
        """Escalation requested outside the voice turn (UI button, REST tool, function call)."""
        state = self.get_or_create(channel_name)
        if state.escalation:
            return state.escalation
        log_start = len(state.change_log)
        record = self._escalate(state, reason, urgency, trigger)
        self._finalize(state, log_start)
        return record

    # ------------------------------------------------------------ persistence
    async def _persist_state(self, state: DealState):
        """
        Task 6.3: Write-through to Redis and Postgres.
        """
        state_dict = state.model_dump()
        state_json = json.dumps(state_dict)

        await redis_client.set(f"deal_state:{state.channel_name}", state_json, expire=86400)

        if async_session_factory:
            try:
                async with async_session_factory() as session:
                    stmt = select(DealStateTable).where(DealStateTable.channel_name == state.channel_name)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    stage = state.stage.value if hasattr(state.stage, "value") else str(state.stage)
                    values = dict(
                        session_id=state.session_id,
                        company=state.company,
                        users=state.users,
                        budget=state.budget,
                        timeline=state.timeline,
                        stage=stage,
                        decision_maker=str(state.decision_maker),
                        competitor_mentioned=state.competitor_mentioned,
                        change_log=[c.model_dump() for c in state.change_log],
                        full_state=state_dict,
                        updated_at=time.time(),
                    )
                    if existing:
                        for key, value in values.items():
                            setattr(existing, key, value)
                    else:
                        session.add(DealStateTable(channel_name=state.channel_name, **values))
                    await session.commit()
            except Exception as e:
                logger.debug(f"Postgres write-through debug: {e}")

deal_state_engine = DealStateEngine()
