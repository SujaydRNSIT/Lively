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
from app.config import settings

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

        # 0. Email Detection in buyer utterance
        email_match = re.search(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', text)
        if email_match:
            new_email = email_match.group(1).strip()
            state.contact_email = new_email
            state.crm_lead.contact_email = new_email
            if state.scheduled_demo and (state.scheduled_demo.get("email") != new_email or "@nextgen.ai" in state.scheduled_demo.get("email", "")):
                state.scheduled_demo["email"] = new_email
                try:
                    email_service.send_demo_confirmation(new_email, state.scheduled_demo)
                    logger.info(f"Auto-dispatched demo invite to newly stated email: {new_email}")
                except Exception as e_dispatch:
                    logger.warning(f"Failed to auto-dispatch demo invite on spoken email: {e_dispatch}")

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
        # If demo is already booked & confirmed, only re-trigger if buyer explicitly asks to reschedule
        is_reschedule_intent = bool(re.search(
            r'\b(?:reschedule|change\s+(?:the\s+)?time|different\s+time|move\s+(?:the\s+)?(?:demo|meeting|walkthrough|call)|can\s+we\s+do\s+(?:another|a\s+different))\b',
            lower
        ))
        if state.scheduled_demo and state.scheduled_demo.get("status") == "CONFIRMED" and not is_reschedule_intent:
            return

        # 7a. Exclude non-scheduling patterns (voice demo inquiries, current call references, greetings)
        is_capability_query = bool(re.search(
            r'\b(?:show|give|hear|see|try|test|do)\s+(?:me\s+)?(?:a\s+)?(?:quick\s+|live\s+)?(?:demo|demonstration)\b'
            r'|\b(?:demo\s+of|demo\s+your|voice\s+demo|product\s+demo)\b'
            r'|\b(?:can|could)\s+you\s+(?:demo|demonstrate)\b',
            lower
        ))
        is_current_call_ref = bool(re.search(
            r'\b(?:on|during|end|start|about|for|finish)\s+(?:this|the|our)\s+call\b'
            r'|\b(?:call\s+latency|call\s+quality|phone\s+call|voice\s+call|this\s+call)\b'
            r'|\bcan\s+you\s+hear\s+me\b'
            r'|\bhow\s+does\s+this\s+call\s+work\b',
            lower
        ))
        is_greeting = bool(re.search(
            r'^\s*(?:hello|hi|hey|good\s+(?:morning|afternoon|evening)|howdy|greetings)[\s!.,?]*$',
            lower
        ))

        # 7b. Explicit Scheduling Intent from Buyer
        explicit_schedule_intent = bool(re.search(
            r'\b(?:schedule|book|reserve|set\s*up|arrange|lock\s*in|organize)\s+(?:a\s+|the\s+|our\s+)?(?:demo|walkthrough|meeting|appointment|session|time\s*slot|call\s+with\s+(?:a|the|your)?\s*architect)\b'
            r'|\b(?:book|schedule|reserve)\s+(?:some\s+)?(?:time|a\s+slot|a\s+call)\b'
            r'|\b(?:send|email)\s+(?:me\s+)?(?:the\s+|a\s+)?(?:calendar\s*invite|calendar\s*link|meeting\s*link|invite)\b'
            r'|\b(?:want|like)\s+to\s+(?:schedule|book|reserve|set\s*up)\s+(?:a\s+)?(?:demo|meeting|walkthrough|call)\b'
            r'|\bcan\s+we\s+(?:schedule|book|reserve|set\s*up)\s+(?:a\s+)?(?:demo|meeting|walkthrough|call)\b',
            lower
        ))

        # 7c. Check if previous agent turn proposed a slot and buyer is agreeing to it
        agent_proposed_slot = False
        if state.transcript:
            for turn in reversed(state.transcript):
                if turn.role in ["agent", "assistant"]:
                    t_low = turn.content.lower()
                    if any(w in t_low for w in ["schedule", "book", "walkthrough", "meet", "tomorrow", "calendar", "slot"]):
                        day_check = self._extract_day(t_low)
                        time_check = self._extract_time(t_low)
                        if (day_check and time_check) or any(phrase in t_low for phrase in ["how about", "would you like to", "shall we", "does that work"]):
                            agent_proposed_slot = True
                    break

        buyer_agreed_slot = bool(re.search(
            r'\b(?:that\s+works|works\s+for\s+me|sounds\s+good|lock\s+it\s+in|let\'?s\s+do\s+(?:that|it|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|\d+\s*(?:am|pm)\s+works|perfect\s+let\'?s\s+do\s+it|yes\s+let\'?s\s+do\s+that|yes\s+please\s+book)\b',
            lower
        ))

        # 7d. Buyer directly specifies day AND time with meeting intention
        direct_day = self._extract_day(lower)
        direct_time = self._extract_time(lower)
        has_meeting_keyword = bool(re.search(r'\b(?:demo|walkthrough|meeting|appointment|slot|call)\b', lower))
        buyer_provided_slot = bool(direct_day and direct_time and (has_meeting_keyword or explicit_schedule_intent))

        is_scheduling_trigger = False
        if not is_capability_query and not is_current_call_ref and not is_greeting:
            if explicit_schedule_intent:
                is_scheduling_trigger = True
            elif agent_proposed_slot and buyer_agreed_slot:
                is_scheduling_trigger = True
            elif buyer_provided_slot:
                is_scheduling_trigger = True
            elif is_reschedule_intent:
                is_scheduling_trigger = True

        if is_scheduling_trigger:
            duration = self._extract_duration(lower)
            allow_agent = bool(agent_proposed_slot and buyer_agreed_slot)
            day = direct_day or self._extract_day(lower, state.transcript, allow_agent_fallback=allow_agent) or "Tomorrow"
            time_str = direct_time or self._extract_time(lower, state.transcript, allow_agent_fallback=allow_agent) or "2:00 PM"

            formatted_slot = f"{day} at {time_str} EST ({duration})"

            # 7d. Resolve Contact Email and auto-dispatch
            email = self._resolve_target_email(state, text)
            state.contact_email = email
            if state.crm_lead:
                state.crm_lead.contact_email = email

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

    def _resolve_target_email(self, state: DealState, text: str = "") -> str:
        # 1. Spoken email in current turn
        if text:
            email_match = re.search(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', text)
            if email_match:
                return email_match.group(1).strip()

        # 2. Registered contact email in DealState
        if state.contact_email and "@" in state.contact_email and "alex.rivera@nextgen.ai" not in state.contact_email:
            return state.contact_email.strip()

        # 3. CRM Lead contact email
        if state.crm_lead and getattr(state.crm_lead, "contact_email", None) and "@" in state.crm_lead.contact_email and "alex.rivera@nextgen.ai" not in state.crm_lead.contact_email:
            return state.crm_lead.contact_email.strip()

        # 4. Spoken email in any prior buyer turn in the transcript
        if state.transcript:
            for turn in reversed(state.transcript):
                if turn.role == "buyer":
                    em = re.search(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', turn.content)
                    if em:
                        return em.group(1).strip()

        # 5. Configured system user/owner email
        clean_user = (settings.SMTP_USER or "").strip()
        clean_from = (settings.SMTP_FROM_EMAIL or "").strip()
        if clean_user and "@" in clean_user:
            return clean_user
        if clean_from and "@" in clean_from:
            return clean_from

        return "anishhyd995@gmail.com"

    def _extract_day(self, lower: str, transcript: Optional[List[ChatTurn]] = None, allow_agent_fallback: bool = False) -> Optional[str]:
        m = re.search(r'\b((?:next|this|coming)?\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|tomorrow|today|day after tomorrow)\b', lower)
        if m:
            return m.group(1).strip().title()
        m2 = re.search(r'\b((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?)\b', lower)
        if m2:
            return m2.group(1).strip().title()
        if allow_agent_fallback and transcript:
            for turn in reversed(transcript):
                if turn.role in ["agent", "assistant"]:
                    t_low = turn.content.lower()
                    m3 = re.search(r'\b((?:next|this|coming)?\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|tomorrow|today|day after tomorrow)\b', t_low)
                    if m3:
                        return m3.group(1).strip().title()
        return None

    def _extract_time(self, lower: str, transcript: Optional[List[ChatTurn]] = None, allow_agent_fallback: bool = False) -> Optional[str]:
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
        m = re.search(r'\b(?:at|around)\s+((?:1[0-2]|0?[1-9]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve))(?!\s*(?:mins|minutes|min|hour|hours|users|seats|reps|percent|k|thousand))\b', lower)
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

        # 6. Keywords with context (NEVER bare "morning" or "afternoon" which catches "Good morning"!)
        if re.search(r'\b(?:in\s+the|tomorrow|this)\s+morning\b', lower):
            return "10:00 AM"
        if re.search(r'\b(?:in\s+the|tomorrow|this)\s+afternoon\b', lower):
            return "2:00 PM"
        if re.search(r'\b(?:in\s+the|tomorrow|this)\s+evening\b', lower):
            return "5:00 PM"

        # 7. Check recent assistant turn only if allow_agent_fallback is True
        if allow_agent_fallback and transcript:
            for turn in reversed(transcript):
                if turn.role in ["agent", "assistant"]:
                    t_val = self._extract_time(turn.content.lower(), None, allow_agent_fallback=False)
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
        Strictly verify that:
        1. scheduled_demo is not already booked.
        2. Agent is explicitly confirming a booked reservation (not just describing features or proposing).
        3. The buyer in recent conversation actually requested or confirmed a demo.
        """
        if state.scheduled_demo and state.scheduled_demo.get("status") == "CONFIRMED":
            return

        lower = text.lower()

        # Must be an explicit agent confirmation of a completed booking
        agent_confirmed = bool(re.search(
            r'\b(?:i\s+have|i\'ve|we\s+have|we\'ve)\s+(?:booked|scheduled|reserved|locked\s+in)\s+(?:a|the|our|your)?\s*(?:demo|walkthrough|meeting|appointment|call|session|slot)\b'
            r'|\b(?:demo|walkthrough|meeting)\s+(?:is|has\s+been)\s+(?:locked\s+in|booked|scheduled|confirmed)\b'
            r'|\bcalendar\s+(?:invite|invitation)\s+(?:has\s+been|is)\s+dispatched\b',
            lower
        ))
        if not agent_confirmed:
            return

        # Verification: Did the buyer actually ask for or agree to a demo?
        buyer_agreed = False
        if state.transcript:
            for turn in reversed(state.transcript):
                if turn.role == "buyer":
                    b_low = turn.content.lower()
                    if re.search(r'\b(schedule|book|reserve|set\s*up|lock\s*in|walkthrough|demo|meeting|that\s+works|works\s+for\s+me|sounds\s+good|yes\s+please|let\'?s\s+do\s+it)\b', b_low):
                        buyer_agreed = True
                        break

        if not buyer_agreed:
            logger.info("Agent mentioned booking confirmation but buyer never requested or agreed to a demo. Skipping false trigger.")
            return

        day = self._extract_day(lower, state.transcript, allow_agent_fallback=True) or "Tomorrow"
        time_str = self._extract_time(lower, state.transcript, allow_agent_fallback=True) or "2:00 PM"
        duration = self._extract_duration(lower)
        formatted_slot = f"{day} at {time_str} EST ({duration})"

        email = self._resolve_target_email(state, text)
        state.contact_email = email
        if state.crm_lead:
            state.crm_lead.contact_email = email

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
