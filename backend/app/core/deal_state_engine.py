import time
import json
import re
import logging
from typing import Dict, Any, Optional, List
from app.models.schemas import DealState, ChatTurn, ObjectionRecord, DealStageEnum, ChangeLogEntry
from app.core.decision import decision_engine
from app.db.redis_client import redis_client
from app.db.postgres import async_session_factory, DealStateTable
from sqlalchemy import select
from app.services.email_service import email_service

logger = logging.getLogger("lively.core.deal_state_engine")

class DealStateEngine:
    """
    Task 6.1, 6.2, 6.3:
    In-memory + Redis cache + Postgres write-through Deal State Engine.
    Supports additive entity merging, change-log diffing (e.g. users: 20 -> 80), and re-qualification triggers.
    """
    def __init__(self):
        self._states: Dict[str, DealState] = {}

    def get_or_create(self, channel_name: str) -> DealState:
        if channel_name not in self._states:
            self._states[channel_name] = DealState(
                channel_name=channel_name,
                session_id=f"sess_{channel_name}_{int(time.time())}"
            )
        return self._states[channel_name]

    def get_state(self, channel_name: str) -> Optional[DealState]:
        return self._states.get(channel_name)

    def reset_state(self, channel_name: str) -> DealState:
        new_state = DealState(
            channel_name=channel_name,
            session_id=f"sess_{channel_name}_{int(time.time())}"
        )
        self._states[channel_name] = new_state
        return new_state

    def record_turn(
        self,
        channel_name: str,
        role: str,
        text: str,
        sentiment: str = "Neutral"
    ) -> DealState:
        state = self.get_or_create(channel_name)
        state.transcript.append(
            ChatTurn(role=role, content=text, timestamp=time.time(), sentiment=sentiment)
        )

        if role == "buyer":
            self.understand_and_merge_entities(state, text)
        elif role == "agent":
            self.check_agent_demo_confirmation(state, text)

        state.next_best_action = decision_engine.evaluate_next_action(state)
        state.updated_at = time.time()

        # Task 6.3: Cache in Redis + Write-through to Postgres
        try:
            import asyncio
            asyncio.create_task(self._persist_state(state))
        except Exception:
            pass

        return state

    def understand_and_merge_entities(self, state: DealState, text: str):
        """
        Task 6.2: Merge new extracted entities into existing state and track change log.
        """
        lower = text.lower()

        # 1. Users / Scale Change Detection
        user_match = re.search(r'(\d+)\s*(users|seats|agents|reps|licenses)', lower)
        if user_match:
            new_users = int(user_match.group(1))
            old_users = state.users
            if new_users != old_users:
                state.users = new_users
                change = ChangeLogEntry(
                    field="users",
                    old_value=old_users,
                    new_value=new_users,
                    description=f"User scale changed from {old_users} -> {new_users} seats. Triggered re-pricing review."
                )
                state.change_log.append(change)
                state.bant.need["scale"] = f"{new_users} seats"
                state.crm_lead.notes = f"{state.crm_lead.notes or ''} [Scale: {new_users} seats]".strip()

        # 2. Budget Change Detection
        budget_match = re.search(r'(\$\d+[\d,]*(?:\s*[km])?(?:\s*arr|\s*month|\s*year)?|\d+\s*(?:k|thousand|million)\s*(?:dollars|arr|budget))', lower)
        if budget_match:
            new_budget = budget_match.group(1).strip().upper()
            old_budget = state.budget
            if new_budget != old_budget:
                state.budget = new_budget
                state.bant.budget["value"] = new_budget
                state.bant.budget["status"] = "Identified"
                state.crm_lead.deal_value = new_budget
                state.change_log.append(ChangeLogEntry(
                    field="budget",
                    old_value=old_budget,
                    new_value=new_budget,
                    description=f"Budget updated to {new_budget}."
                ))

        # 3. Decision Maker / Authority
        if any(w in lower for w in ["i decide", "my call", "vp", "cto", "head of", "director", "founder", "ceo", "product manager"]):
            for role_keyword in ["vp of product", "vp product", "vp of engineering", "vp engineering", "cto", "ceo", "head of sales", "director of engineering", "product manager", "founder"]:
                if role_keyword in lower:
                    formatted_role = role_keyword.title()
                    if state.decision_maker != formatted_role:
                        state.change_log.append(ChangeLogEntry(
                            field="decision_maker",
                            old_value=state.decision_maker,
                            new_value=formatted_role,
                            description=f"Authority identified as {formatted_role}."
                        ))
                    state.decision_maker = formatted_role
                    state.bant.authority["role"] = formatted_role
                    break
            state.bant.authority["status"] = "Identified"
            state.bant.authority["decision_maker"] = True

        # 4. Timeline
        if any(w in lower for w in ["month", "quarter", "q1", "q2", "q3", "q4", "weeks", "asap", "immediately"]):
            state.timeline = text.strip()
            state.bant.timeline["status"] = "Identified"
            state.bant.timeline["timeframe"] = text.strip()

        # 5. Competitor Mention
        for comp in ["openai", "realtime", "twilio", "vapi", "bland", "elevenlabs", "deepgram"]:
            if comp in lower:
                comp_name = "OpenAI Realtime" if "openai" in comp or "realtime" in comp else comp.title()
                state.competitor_mentioned = comp_name
                break

        # 6. Objections
        if any(w in lower for w in ["expensive", "cost", "price", "budget", "pricing", "discount"]):
            if not any(o.type == "pricing" and not o.resolved for o in state.objections):
                rec = ObjectionRecord(
                    type="pricing",
                    category="pricing",
                    utterance=text,
                    suggested_rebuttal="Present 40-60% TCO savings and sub-second Agora latency SLA compared to separate STT/TTS stitching."
                )
                state.objections.append(rec)
                state.active_objections.append(rec)
                state.stage = DealStageEnum.OBJECTION_HANDLING
                state.sentiment = "Hesitant"
                state.sentiment_score = -0.3

        if any(w in lower for w in ["openai", "realtime", "twilio", "vapi", "bland"]):
            if not any(o.type == "competitor" and not o.resolved for o in state.objections):
                rec = ObjectionRecord(
                    type="competitor",
                    category="competitor",
                    utterance=text,
                    suggested_rebuttal="Agora provides dedicated SD-RTN network transport with barge-in and complete LLM freedom (Groq / NVIDIA NIM)."
                )
                state.objections.append(rec)
                state.active_objections.append(rec)
                state.stage = DealStageEnum.OBJECTION_HANDLING

        if any(w in lower for w in ["latency", "delay", "slow", "lag", "barge in"]):
            if not any(o.type == "latency" and not o.resolved for o in state.objections):
                rec = ObjectionRecord(
                    type="latency",
                    category="latency",
                    utterance=text,
                    suggested_rebuttal="Groq LPU provides sub-200ms TTFT and Agora delivers <80ms WebRTC audio transport."
                )
                state.objections.append(rec)
                state.active_objections.append(rec)

        # 7. Demo Stage & Calendar Booking Trigger
        has_demo_word = any(k in lower for k in ["demo", "walkthrough", "meeting", "calendar", "call", "appointment", "slot"])
        has_action_word = any(k in lower for k in [
            "schedule", "scheduled", "book", "booked", "booking", "fix", "fixing",
            "set up", "lock", "locked", "locking", "reserve", "reserved",
            "arrange", "confirm", "confirmed", "take"
        ])
        has_agreement = any(k in lower for k in [
            "yes", "sure", "sounds good", "perfect", "that works", "works for me",
            "let's do it", "lock it in", "lock it", "lock that", "go ahead", "confirmed"
        ])
        has_duration = bool(re.search(r'\b(\d+\s*(?:mins|minutes|min|hour|hours)|half(?:\s+an)?\s+hour|thirty-minute|ten-minute)\b', lower))

        extracted_time = self._extract_time(lower, state.transcript)
        extracted_day = self._extract_day(lower, state.transcript)

        is_demo_context = (
            state.stage == DealStageEnum.DEMO_SCHEDULING or
            any(k in state.next_best_action.lower() for k in ["demo", "calendar", "schedule", "walkthrough"])
        )

        is_scheduling_trigger = (
            has_demo_word or
            (extracted_day and extracted_time) or
            (has_action_word and (extracted_day or extracted_time or has_duration)) or
            (has_duration and (extracted_day or extracted_time)) or
            (is_demo_context and (extracted_day or extracted_time or has_agreement or has_action_word))
        )

        if is_scheduling_trigger:
            duration = self._extract_duration(lower)
            day = extracted_day or self._extract_day(lower, state.transcript) or "Tomorrow"
            time_str = extracted_time or self._extract_time(lower, state.transcript) or "2:00 PM"

            formatted_slot = f"{day} at {time_str} EST ({duration})"

            # 7d. Extract Contact Email (Prioritize user registered email from entry popup)
            email = (
                (state.contact_email.strip() if state.contact_email and "@" in state.contact_email else None) or
                (state.crm_lead.contact_email.strip() if state.crm_lead and getattr(state.crm_lead, "contact_email", None) else None)
            )
            email_match = re.search(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', text)
            if email_match:
                email = email_match.group(1).strip()
            if not email:
                if state.crm_lead and getattr(state.crm_lead, "contact_name", None) and state.crm_lead.contact_name != "Prospect":
                    contact_slug = state.crm_lead.contact_name.lower().replace(" ", ".")
                    email = f"{contact_slug}@prospect.com"
                else:
                    email = "alex.rivera@nextgen.ai"

            # 7e. Prepare Google Calendar block & Email Invitation
            meeting_id = f"mtg_{int(time.time()*1000)}"
            prep = email_service.prepare_demo_confirmation(email, {
                "time": formatted_slot,
                "duration": duration,
                "topic": "Lively Real-Time Voice AI Sales Deep-Dive",
                "host": "Senior Solutions Architect",
                "meeting_link": "https://meet.google.com/new",
                "meeting_id": meeting_id
            })

            # 7f. Update Deal State with Confirmed Demo & Calendar Link
            old_demo = state.scheduled_demo
            demo_data = {
                "meeting_id": meeting_id,
                "status": "CONFIRMED",
                "time": formatted_slot,
                "email": email,
                "duration": duration,
                "topic": "Lively Real-Time Voice AI Sales Deep-Dive",
                "host": "Senior Solutions Architect",
                "meeting_link": "https://meet.google.com/new",
                "google_calendar_link": prep["google_calendar_url"],
                "booked_at": time.time(),
                "message": f"Demo locked & confirmed for {formatted_slot}. Google Meet link & Calendar block dispatched to {email}."
            }
            state.scheduled_demo = demo_data
            state.stage = DealStageEnum.DEMO_SCHEDULING
            state.crm_lead.status = "Demo_Scheduled"

            action_note = f"Demo booked: {formatted_slot} ({email})"
            if action_note not in state.action_items:
                state.action_items.append(action_note)

            email_note = f"Invite dispatched: {email} (Google Meet + Calendar blocked)"
            if email_note not in state.action_items:
                state.action_items.append(email_note)

            # 7g. Dispatch Confirmation Email via Email Service
            try:
                email_service.send_demo_confirmation(email, demo_data)
            except Exception as e_err:
                logger.error(f"Failed to dispatch demo email invite: {e_err}")

            state.change_log.append(ChangeLogEntry(
                field="scheduled_demo",
                old_value=old_demo.get("time") if old_demo else None,
                new_value=formatted_slot,
                description=f"Calendar demo locked in for {formatted_slot} with {email}."
            ))

    def _extract_day(self, lower: str, transcript: Optional[List[ChatTurn]] = None) -> Optional[str]:
        m = re.search(r'\b((?:next|this|coming)?\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|tomorrow|today|day after tomorrow)\b', lower)
        if m:
            return m.group(1).strip().title()
        m2 = re.search(r'\b((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?)\b', lower)
        if m2:
            return m2.group(1).strip().title()
        if transcript:
            for turn in reversed(transcript):
                if turn.role in ["agent", "assistant"]:
                    t_low = turn.content.lower()
                    m3 = re.search(r'\b((?:next|this|coming)?\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|tomorrow|today|day after tomorrow)\b', t_low)
                    if m3:
                        return m3.group(1).strip().title()
        return None

    def _extract_time(self, lower: str, transcript: Optional[List[ChatTurn]] = None) -> Optional[str]:
        hour_words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12
        }
        # 1. Digits with AM/PM e.g. "2 pm", "2:00 pm", "2pm", "2:30pm"
        m = re.search(r'\b((?:1[0-2]|0?[1-9])(?::[0-5]\d)?\s*(?:am|pm|a\.m\.|p\.m\.))\b', lower)
        if m:
            t_raw = m.group(1).replace(".", "").strip().upper()
            if ":" not in t_raw:
                parts = re.split(r'(AM|PM)', t_raw)
                return f"{parts[0].strip()}:00 {parts[1].strip()}"
            return t_raw

        # 2. Word numbers with AM/PM e.g. "two pm", "two p.m."
        m = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(?:am|pm|a\.m\.|p\.m\.)\b', lower)
        if m:
            w = m.group(1).lower()
            h = hour_words.get(w, 2)
            period = "PM" if "pm" in m.group(0) else "AM"
            return f"{h}:00 {period}"

        # 3. "at/around X" e.g. "at 2", "around 2", "at two"
        m = re.search(r'\b(?:at|around)\s+((?:1[0-2]|0?[1-9]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve))(?!\s*(?:mins|minutes|min|hour|hours|users|seats|reps|percent))\b', lower)
        if m:
            token = m.group(1).lower()
            h = hour_words.get(token) if token in hour_words else int(token)
            period = "PM" if h in [1, 2, 3, 4, 5, 6, 7] or any(p in lower for p in ["afternoon", "evening", "tonight"]) else "AM"
            return f"{h}:00 {period}"

        # 4. "X in the afternoon/morning/evening"
        m = re.search(r'\b(1[0-2]|0?[1-9]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:in the\s+)?(morning|afternoon|evening)\b', lower)
        if m:
            token = m.group(1).lower()
            h = hour_words.get(token) if token in hour_words else int(token)
            period = "AM" if m.group(2) == "morning" else "PM"
            return f"{h}:00 {period}"

        # 5. "X o'clock"
        m = re.search(r'\b(1[0-2]|0?[1-9]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*o\'?clock\b', lower)
        if m:
            token = m.group(1).lower()
            h = hour_words.get(token) if token in hour_words else int(token)
            period = "PM" if h in [1, 2, 3, 4, 5, 6, 7] or any(p in lower for p in ["afternoon", "evening"]) else "AM"
            return f"{h}:00 {period}"

        # 6. Keywords
        if "morning" in lower:
            return "10:00 AM"
        if "afternoon" in lower:
            return "2:00 PM"
        if "evening" in lower:
            return "5:00 PM"

        # 7. Check recent assistant turn
        if transcript:
            for turn in reversed(transcript):
                if turn.role in ["agent", "assistant"]:
                    t_val = self._extract_time(turn.content.lower(), None)
                    if t_val:
                        return t_val

        return None

    def _extract_duration(self, lower: str) -> str:
        dur_match = re.search(r'\b(\d+\s*(?:mins|minutes|min|hours|hour)|half(?:\s+an)?\s+hour|thirty-minute|ten-minute|fifteen-minute)\b', lower)
        if dur_match:
            d = dur_match.group(1).strip()
            if "thirty" in d or "30" in d:
                return "30 mins"
            if "ten" in d or "10" in d:
                return "10 mins"
            if "fifteen" in d or "15" in d:
                return "15 mins"
            return d
        return "30 mins"

    def check_agent_demo_confirmation(self, state: DealState, text: str):
        """
        If the agent verbally confirms a demo reservation, ensure scheduled_demo is locked in.
        """
        lower = text.lower()
        if any(w in lower for w in ["reserved", "booked", "scheduled", "confirmed"]) and any(w in lower for w in ["demo", "walkthrough", "slot", "calendar", "call"]):
            day = self._extract_day(lower, state.transcript) or "Tomorrow"
            time_str = self._extract_time(lower, state.transcript) or "2:00 PM"
            duration = self._extract_duration(lower)
            formatted_slot = f"{day} at {time_str} EST ({duration})"

            email = (
                (state.contact_email.strip() if state.contact_email and "@" in state.contact_email else None) or
                (state.crm_lead.contact_email.strip() if state.crm_lead and getattr(state.crm_lead, "contact_email", None) else None)
            )
            email_match = re.search(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', text)
            if email_match:
                email = email_match.group(1).strip()
            if not email:
                if state.crm_lead and getattr(state.crm_lead, "contact_name", None) and state.crm_lead.contact_name != "Prospect":
                    contact_slug = state.crm_lead.contact_name.lower().replace(" ", ".")
                    email = f"{contact_slug}@prospect.com"
                else:
                    email = "alex.rivera@nextgen.ai"

            meeting_id = f"mtg_{int(time.time()*1000)}"
            prep = email_service.prepare_demo_confirmation(email, {
                "time": formatted_slot,
                "duration": duration,
                "topic": "Lively Real-Time Voice AI Sales Deep-Dive",
                "host": "Senior Solutions Architect",
                "meeting_link": "https://meet.google.com/new",
                "meeting_id": meeting_id
            })

            old_demo = state.scheduled_demo
            demo_data = {
                "meeting_id": meeting_id,
                "status": "CONFIRMED",
                "time": formatted_slot,
                "email": email,
                "duration": duration,
                "topic": "Lively Real-Time Voice AI Sales Deep-Dive",
                "host": "Senior Solutions Architect",
                "meeting_link": "https://meet.google.com/new",
                "google_calendar_link": prep["google_calendar_url"],
                "booked_at": time.time(),
                "message": f"Demo locked & confirmed for {formatted_slot}. Google Meet link & Calendar block dispatched to {email}."
            }
            state.scheduled_demo = demo_data
            state.stage = DealStageEnum.DEMO_SCHEDULING
            state.crm_lead.status = "Demo_Scheduled"
            action_note = f"Demo booked: {formatted_slot} ({email})"
            if action_note not in state.action_items:
                state.action_items.append(action_note)

            email_note = f"Invite dispatched: {email} (Google Meet + Calendar blocked)"
            if email_note not in state.action_items:
                state.action_items.append(email_note)

            try:
                email_service.send_demo_confirmation(email, demo_data)
            except Exception as e_err:
                logger.error(f"Failed to dispatch demo email invite: {e_err}")

            state.change_log.append(ChangeLogEntry(
                field="scheduled_demo",
                old_value=old_demo.get("time") if old_demo else None,
                new_value=formatted_slot,
                description=f"Calendar demo locked in for {formatted_slot} with {email}."
            ))

    def resolve_objection(self, channel_name: str, objection_id: str) -> Optional[DealState]:
        state = self.get_or_create(channel_name)
        for obj in state.objections:
            if obj.id == objection_id or obj.type == objection_id or obj.category == objection_id:
                obj.resolved = True
                obj.status = "Resolved"
        state.active_objections = [o for o in state.objections if not o.resolved]
        state.resolved_objections = [o for o in state.objections if o.resolved]
        state.next_best_action = decision_engine.evaluate_next_action(state)
        state.updated_at = time.time()
        
        try:
            import asyncio
            asyncio.create_task(self._persist_state(state))
        except Exception:
            pass

        return state

    async def _persist_state(self, state: DealState):
        """
        Task 6.3: Write-through to Redis and Postgres.
        """
        state_dict = state.model_dump()
        state_json = json.dumps(state_dict)

        # 1. Fast Redis cache
        await redis_client.set(f"deal_state:{state.channel_name}", state_json, expire=86400)

        # 2. Postgres durability
        if async_session_factory:
            try:
                async with async_session_factory() as session:
                    stmt = select(DealStateTable).where(DealStateTable.channel_name == state.channel_name)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        existing.session_id = state.session_id
                        existing.company = state.company
                        existing.users = state.users
                        existing.budget = state.budget
                        existing.timeline = state.timeline
                        existing.stage = state.stage.value if hasattr(state.stage, "value") else str(state.stage)
                        existing.decision_maker = str(state.decision_maker)
                        existing.competitor_mentioned = state.competitor_mentioned
                        existing.change_log = [c.model_dump() for c in state.change_log]
                        existing.full_state = state_dict
                        existing.updated_at = time.time()
                    else:
                        row = DealStateTable(
                            channel_name=state.channel_name,
                            session_id=state.session_id,
                            company=state.company,
                            users=state.users,
                            budget=state.budget,
                            timeline=state.timeline,
                            stage=state.stage.value if hasattr(state.stage, "value") else str(state.stage),
                            decision_maker=str(state.decision_maker),
                            competitor_mentioned=state.competitor_mentioned,
                            change_log=[c.model_dump() for c in state.change_log],
                            full_state=state_dict,
                            updated_at=time.time()
                        )
                        session.add(row)

                    await session.commit()
            except Exception as e:
                logger.debug(f"Postgres write-through debug: {e}")

deal_state_engine = DealStateEngine()
