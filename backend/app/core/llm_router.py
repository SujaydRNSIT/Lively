import time
import re
import asyncio
import logging
import statistics
from collections import deque
from typing import AsyncGenerator, Callable, List, Dict, Any, Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential
from groq import AsyncGroq
from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import DealState
from app.core.prompts import LIVELY_SYSTEM_PROMPT
from app.core.decision import decision_engine
from app.core.background import spawn
from app.routers.telemetry import ws_manager

logger = logging.getLogger("lively.core.llm_router")

GUARD_TEXT = "I can only help with questions about Lively and our voice AI platform. How can I help your business today?"


class LatencyTracker:
    """
    Task 5.3: Latency budget instrumentation.
    TTFT = request arrival at the backend -> first spoken token sent back to Agora.
    Total = request arrival -> end of the streamed answer. No numbers are reported until turns are measured.
    """
    def __init__(self, max_samples: int = 500):
        self.ttft_records: deque = deque(maxlen=max_samples)
        self.total_turn_records: deque = deque(maxlen=max_samples)
        self.model_turn_counts: Dict[str, int] = {"groq": 0, "nvidia_nim": 0, "builtin_fallback": 0}
        self.failovers = 0
        self.partial_turns = 0

    def record(self, model_name: str, ttft_ms: Optional[float], total_ms: float, partial: bool = False):
        if ttft_ms is not None:
            self.ttft_records.append(ttft_ms)
        self.total_turn_records.append(total_ms)
        name = model_name.lower()
        provider = "groq" if name.startswith("groq") else ("nvidia_nim" if name.startswith("nvidia") else "builtin_fallback")
        self.model_turn_counts[provider] = self.model_turn_counts.get(provider, 0) + 1
        if partial:
            self.partial_turns += 1

    @staticmethod
    def _pct(values, q: float) -> float:
        ordered = sorted(values)
        return round(ordered[min(len(ordered) - 1, int(len(ordered) * q))], 2)

    def get_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "total_turns": len(self.total_turn_records),
            "measured": bool(self.ttft_records),
            "model_breakdown": dict(self.model_turn_counts),
            "failovers": self.failovers,
            "partial_turns": self.partial_turns,
            "ttft_p50_ms": None,
            "ttft_p95_ms": None,
            "ttft_mean_ms": None,
            "ttft_min_ms": None,
            "total_turn_p50_ms": None,
            "total_turn_p95_ms": None,
        }
        if self.ttft_records:
            stats.update({
                "ttft_p50_ms": self._pct(self.ttft_records, 0.5),
                "ttft_p95_ms": self._pct(self.ttft_records, 0.95),
                "ttft_mean_ms": round(statistics.mean(self.ttft_records), 2),
                "ttft_min_ms": round(min(self.ttft_records), 2),
            })
        if self.total_turn_records:
            stats.update({
                "total_turn_p50_ms": self._pct(self.total_turn_records, 0.5),
                "total_turn_p95_ms": self._pct(self.total_turn_records, 0.95),
            })
        return stats

latency_tracker = LatencyTracker()


def make_chunk(chunk_id: str, model: str, content: str, finish_reason=None) -> str:
    import json
    chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


def make_role_chunk(chunk_id: str, model: str) -> str:
    import json
    chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


_SPOKEN_NUMBERS = {"10": "ten", "15": "fifteen", "20": "twenty", "30": "thirty", "45": "forty-five", "60": "sixty"}
# Only bare numbers: never digits inside times (2:30), amounts ($30, 10,000), decimals or percentages.
_DURATION_NUMBER_RE = re.compile(r"(?<![\w:.,$/])(10|15|20|30|45|60)-min(?:ute)?s?\b", re.I)
_STANDALONE_NUMBER_RE = re.compile(r"(?<![\w:.,$/])(10|15|20|30)(?![\w:.,/%])")


def normalize_spoken_numbers(text: str) -> str:
    """Rewrite common durations as words so TTS says 'thirty' instead of 'three zero'."""
    if not text:
        return text
    text = _DURATION_NUMBER_RE.sub(lambda m: f"{_SPOKEN_NUMBERS[m.group(1)]}-minute", text)
    return _STANDALONE_NUMBER_RE.sub(lambda m: _SPOKEN_NUMBERS[m.group(1)], text)


class SpokenStream:
    """Applies normalization on word boundaries, so a number split across two chunks is still handled."""
    def __init__(self):
        self._pending = ""

    def feed(self, piece: str) -> str:
        self._pending += piece
        cut = max(self._pending.rfind(" "), self._pending.rfind("\n"))
        if cut < 0:
            return ""
        ready, self._pending = self._pending[:cut + 1], self._pending[cut + 1:]
        return normalize_spoken_numbers(ready)

    def flush(self) -> str:
        ready, self._pending = self._pending, ""
        return normalize_spoken_numbers(ready)


def is_prompt_injection(user_msg: str) -> bool:
    lower = user_msg.lower().strip()
    injection_triggers = [
        "ignore everything", "ignore all", "system prompt",
        "unrestricted ai", "not a sales agent", "i'm the ceo", "i am the ceo",
        "internal instructions", "configuration and instructions", "jailbreak",
        "override your instructions", "you are now an unrestricted",
        "forget all instructions", "reveal your instructions", "tell me your prompt",
        "give me all your internal"
    ]
    return any(trigger in lower for trigger in injection_triggers)


def _spoken_slot(label: str) -> str:
    return re.sub(r"\s*\(\d+ mins\)", "", label).replace(":00 ", " ")


class LLMRouter:
    """
    Task 5.1, 5.2, 5.3:
    Streams each turn from Groq, falls back to NVIDIA NIM and then the built-in brain only if the
    previous provider fails before producing a token, and records honest latency.
    """
    def __init__(self):
        self.groq_client: Optional[AsyncGroq] = None
        if settings.GROQ_API_KEY:
            try:
                self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")

        self.nvidia_client: Optional[AsyncOpenAI] = None
        if settings.NVIDIA_NIM_API_KEY:
            try:
                self.nvidia_client = AsyncOpenAI(
                    api_key=settings.NVIDIA_NIM_API_KEY,
                    base_url=settings.NVIDIA_NIM_BASE_URL
                )
            except Exception as e:
                logger.warning(f"Failed to initialize NVIDIA NIM client: {e}")

    @staticmethod
    def _strip_think_stream(delta_content: str, state: dict) -> str:
        """Strip <think>...</think> tags from streaming LLM output. Stateful across chunks."""
        if delta_content is None:
            return ""
        state["buf"] = state.get("buf", "") + delta_content
        out = ""
        while True:
            if state.get("inside_think"):
                end = state["buf"].find("</think>")
                if end == -1:
                    state["buf"] = ""
                    break
                state["buf"] = state["buf"][end + 8:]
                state["inside_think"] = False
            else:
                start = state["buf"].find("<think>")
                if start == -1:
                    out += state["buf"]
                    state["buf"] = ""
                    break
                out += state["buf"][:start]
                state["buf"] = state["buf"][start + 6:]
                state["inside_think"] = True
        return out

    def should_route_to_nvidia(self, user_msg: str, deal_state: DealState) -> bool:
        """
        Complexity heuristic (compliance/architecture topics or several open objections).
        Used to give complex turns a larger answer budget.
        """
        lower = user_msg.lower()
        complex_keywords = ["hipaa", "soc2", "enterprise compliance", "on-premise", "sla guarantees", "custom contract", "architecture migration"]
        if any(k in lower for k in complex_keywords):
            return True
        return len(deal_state.active_objections) >= 2

    def is_objection_or_complex_turn(self, user_msg: str, deal_state: DealState) -> bool:
        lower = user_msg.lower()
        objection_triggers = [
            "expensive", "too much", "cost too", "price", "budget", "pricing",
            "competitor", "openai", "twilio", "vapi", "bland", "why should",
            "security", "hipaa", "soc2", "compliance", "not sure", "skeptical",
            "hard to", "difficult", "switch", "replace", "architecture", "trust"
        ]
        if any(k in lower for k in objection_triggers):
            return True
        if deal_state and len(deal_state.active_objections) > 0:
            return True
        return self.should_route_to_nvidia(user_msg, deal_state)

    def construct_system_prompt(self, deal_state: DealState, latest_user_msg: str) -> str:
        rag_context = decision_engine.retrieve_context(latest_user_msg)
        bant = deal_state.bant
        dimensions = ("budget", "authority", "need", "timeline")
        known = [d for d in dimensions if getattr(bant, d).get("status") == "Identified"]
        missing = [d for d in dimensions if d not in known]
        qualification = (f"{deal_state.qualification_score}/100{' (lead qualified)' if deal_state.lead_qualified else ''}; "
                         f"known: {', '.join(known) or 'nothing yet'}; still unknown: {', '.join(missing) or 'none'}")

        objections = ", ".join(f"{o.type} (raised {o.times_raised}x)" for o in deal_state.active_objections) or "None"

        demo = deal_state.scheduled_demo if deal_state.scheduled_demo and deal_state.scheduled_demo.get("status") == "CONFIRMED" else None
        if demo:
            scheduled_demo = f"CONFIRMED for {demo['time']}" + (f", invite going to {demo['email']}" if demo.get("email") else ", NO EMAIL ON FILE YET")
        else:
            scheduled_demo = "None"

        if deal_state.slot_conflict:
            conflict = deal_state.slot_conflict
            scheduling_note = (f"Requested {conflict.get('requested')} is unavailable because {conflict.get('reason')}. "
                               f"Offer instead: {', '.join(conflict.get('alternatives') or []) or 'the open slots'}.")
        elif deal_state.pending_demo_request:
            scheduling_note = "Buyer wants a demo but hasn't picked a time. Offer two or three open slots."
        else:
            scheduling_note = "Nothing pending."

        escalation = (f"IN PROGRESS ({deal_state.escalation.get('reason')}). An account executive is joining with the full context."
                      if deal_state.escalation else "None")

        role = bant.authority.get("role") or "Unknown"
        decision_maker = bant.authority.get("decision_maker")
        if decision_maker is True:
            role += " (decision maker)"
        elif decision_maker is False:
            role += " (not the final decision maker)"

        dd = deal_state.deal_desk
        if dd:
            status = dd.get("status")
            auth_pct = float(dd.get("authorised_pct") or 0)
            prop_pct = float(dd.get("proposed_pct") or 0)
            if status == "approved":
                concession_status = f"APPROVED concession of {auth_pct:.0f}% off. Quote the deduced price to the buyer (e.g. Starter $199/mo becomes ${(199*(1-auth_pct/100)):.0f}/mo; Growth $699/mo becomes ${(699*(1-auth_pct/100)):.0f}/mo)."
            elif status == "pending_manager":
                concession_status = f"PENDING manager approval for {prop_pct:.0f}%. Inform the buyer that discounts above 15% require manager sign-off or an annual commitment."
            elif status == "refused":
                concession_status = f"REFUSED concession ({prop_pct:.0f}% exceeds corporate hard ceiling of 25%). Firmly and politely decline the discount."
            else:
                concession_status = "None"
        else:
            concession_status = "Standard pricing. You may grant up to 15% discount autonomously if negotiated."

        stage_val = deal_state.stage.value if hasattr(deal_state.stage, "value") else str(deal_state.stage)
        return LIVELY_SYSTEM_PROMPT.format(
            stage=stage_val,
            qualification=qualification,
            buyer_persona=deal_state.buyer_persona,
            sentiment=deal_state.sentiment,
            budget=bant.budget.get("value") or "Unknown",
            authority=role,
            need=", ".join(bant.need.get("pain_points") or []) or "Unknown",
            timeline=bant.timeline.get("timeframe") or "Unknown",
            seats=deal_state.users or "Unknown",
            active_objections=objections,
            scheduled_demo=scheduled_demo,
            scheduling_note=scheduling_note,
            available_slots=", ".join(deal_state.available_slots) or "None in the next three weeks",
            escalation=escalation,
            concession_status=concession_status,
            next_best_action=deal_state.next_best_action,
            rag_context=rag_context
        )

    async def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        deal_state: DealState,
        channel_name: str,
        model: Optional[str] = None,
        request_started_at: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        started = request_started_at if request_started_at is not None else time.perf_counter()
        chunk_id = f"chatcmpl-{channel_name}-{int(time.time()*1000)}"

        latest_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                latest_user_msg = m.get("content", "")
                break

        yield make_role_chunk(chunk_id, "lively-router")

        sources: List[Tuple[str, Callable[[], AsyncGenerator[str, None]]]] = []
        if is_prompt_injection(latest_user_msg):
            sources.append(("security-guard", lambda: self._stream_text(GUARD_TEXT)))
        else:
            base_tokens = 200 if "gpt-oss" in settings.GROQ_MODEL.lower() else 90
            complex_tokens = 250 if "gpt-oss" in settings.GROQ_MODEL.lower() else 130
            max_tokens = complex_tokens if self.is_objection_or_complex_turn(latest_user_msg, deal_state) else base_tokens
            augmented = [{"role": "system", "content": self.construct_system_prompt(deal_state, latest_user_msg)}]
            augmented += [m for m in messages if m.get("role") != "system"]
            if self.groq_client:
                sources.append((f"groq:{settings.GROQ_MODEL}",
                                lambda: self._stream_provider(self.groq_client, settings.GROQ_MODEL, augmented, max_tokens)))
            if self.nvidia_client:
                sources.append((f"nvidia:{settings.NVIDIA_NIM_MODEL}",
                                lambda: self._stream_provider(self.nvidia_client, settings.NVIDIA_NIM_MODEL, augmented, max_tokens)))
            sources.append(("builtin-sales-brain", lambda: self._stream_text(self._fallback_reply(latest_user_msg, deal_state))))

        provider_used = sources[-1][0]
        first_token_at: Optional[float] = None
        partial = False
        for name, open_stream in sources:
            spoken = SpokenStream()
            emitted = False
            try:
                async for piece in open_stream():
                    text = spoken.feed(piece)
                    if text:
                        first_token_at = first_token_at or time.perf_counter()
                        emitted = True
                        yield make_chunk(chunk_id, name, text)
                tail = spoken.flush()
                if tail:
                    first_token_at = first_token_at or time.perf_counter()
                    emitted = True
                    yield make_chunk(chunk_id, name, tail)
                if not emitted:
                    logger.warning(f"{name} returned an empty answer; trying the next provider.")
                    latency_tracker.failovers += 1
                    continue
                provider_used = name
                break
            except Exception as e:
                if emitted:
                    # The buyer already heard part of this answer: end cleanly rather than restart on another model.
                    logger.warning(f"{name} failed mid-answer ({e}); ending the turn without restarting.")
                    provider_used = name
                    partial = True
                    break
                logger.warning(f"{name} failed before its first token ({e}); trying the next provider.")
                latency_tracker.failovers += 1

        yield make_chunk(chunk_id, provider_used, "", finish_reason="stop")
        yield "data: [DONE]\n\n"

        ttft_ms = (first_token_at - started) * 1000 if first_token_at else None
        total_ms = (time.perf_counter() - started) * 1000
        latency_tracker.record(provider_used, ttft_ms, total_ms, partial=partial)
        logger.info(f"Turn completed by [{provider_used}] -> TTFT: {ttft_ms if ttft_ms is None else round(ttft_ms, 1)}ms, Total: {total_ms:.1f}ms")

        spawn(ws_manager.broadcast_state, channel_name, {
            "type": "LATENCY_UPDATE",
            "data": {
                "active_model": provider_used,
                "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
                "total_ms": round(total_ms, 1),
                "stats": latency_tracker.get_stats()
            }
        })

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4), reraise=True)
    async def _open_stream(self, client: Any, model_name: str, messages: List[Dict[str, str]], max_tokens: int) -> Any:
        """Retries only the connection/request, which is safe: nothing has been spoken yet."""
        return await client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
            temperature=0.5,
            top_p=0.9,
            max_tokens=max_tokens,
        )

    async def _stream_provider(self, client: Any, model_name: str, messages: List[Dict[str, str]], max_tokens: int) -> AsyncGenerator[str, None]:
        response = await self._open_stream(client, model_name, messages, max_tokens)
        think_state: dict = {}
        async for chunk in response:
            raw = chunk.choices[0].delta.content if chunk.choices else None
            content = self._strip_think_stream(raw, think_state)
            if content:
                yield content

    @staticmethod
    async def _stream_text(text: str) -> AsyncGenerator[str, None]:
        for i, word in enumerate(text.split(" ")):
            yield word if i == 0 else f" {word}"
            await asyncio.sleep(0)

    def _fallback_reply(self, user_msg: str, deal_state: DealState) -> str:
        """Built-in brain used only when no LLM is reachable. State-driven first, then keyword replies."""
        lower = user_msg.lower().strip()
        state = deal_state
        demo = state.scheduled_demo if state and state.scheduled_demo and state.scheduled_demo.get("status") == "CONFIRMED" else None
        recent = [e for e in (state.change_log if state else []) if time.time() - e.timestamp < 5]

        if is_prompt_injection(user_msg):
            return GUARD_TEXT
        if state and state.escalation:
            return ("Of course. I'm bringing in one of our account executives now, and they'll have everything we've covered, "
                    "so you won't need to repeat yourself.")
        if state and state.slot_conflict:
            options = " or ".join(_spoken_slot(s) for s in (state.slot_conflict.get("alternatives") or [])[:2]) or "another time"
            return f"That time doesn't work on our side because {state.slot_conflict.get('reason')}. I can do {options}. Which suits you?"
        if demo and any(e.field == "scheduled_demo" for e in recent):
            if demo.get("email"):
                return f"You're all set for {_spoken_slot(demo['time'])}. The invite with the video room link is on its way to {demo['email']}."
            return f"You're booked for {_spoken_slot(demo['time'])}. What's the best email to send the invite to?"
        if demo and any(e.field == "contact_email" for e in recent):
            return f"Got it, the invite for {_spoken_slot(demo['time'])} is on its way to {demo.get('email')}."
        if state and state.pending_demo_request:
            slots = state.available_slots[:2]
            if slots:
                return f"Sure. I can do {' or '.join(_spoken_slot(s) for s in slots)}. Which works better?"
        if state and any(e.field == "demo_declined" for e in recent):
            return "No problem at all. We can pick a time whenever you're ready."

        # Memory questions answered from the deal state
        if re.search(r"\b(?:what(?:'s| is| was) my company|which company|my company called)\b", lower):
            known = state and state.company not in ("Prospective Client", "", None)
            return f"You're with {state.company}." if known else "You haven't mentioned your company yet. Who are you with?"
        if re.search(r"\bhow many (?:users|seats)\b", lower):
            return f"You mentioned {state.users} seats." if state and state.users else "We haven't talked seat count yet. Roughly how many people would use it?"

        if any(w in lower for w in ["audible", "hear me", "can you hear", "microphone", "mic test", "testing"]):
            return "I hear you loud and clear! How are things going today?"
        if any(w in lower for w in ["not convinced", "why exactly should i change", "migrating everything"]):
            return "Those are fair reasons to stay put. If your current tool works and is cheaper, switching only makes sense with clear ROI and no workflow disruption."
        if any(w in lower for w in ["three people", "talked to three", "explain everything again"]):
            return "You shouldn't have to repeat yourself. Let's pick it up right where you left off. What would you like to focus on?"
        if any(w in lower for w in ["frustrated", "useless", "every ai tool"]):
            return "Fair enough. A lot of bots out there are clunky phone trees. What let you down the most with the tools you've tried?"
        if any(w in lower for w in ["don't trust ai", "wrong answer", "hallucinat", "make things up", "how do i know"]):
            return "Totally valid concern. The agent only answers from your approved documentation, and if it's ever unsure it routes the call to a human rep."
        if any(w in lower for w in ["chatbot", "chat bot", "just a bot", "are you a bot"]):
            return "Not a text chatbot, no. It's a real-time voice agent that handles interruptions naturally and qualifies leads like a rep would."
        if any(w in lower for w in ["cricket", "match yesterday", "who won", "football", "weather"]):
            return "I don't have the score handy! Anything I can help you with on Lively?"
        if "website" in lower and any(w in lower for w in ["cost", "price", "pricing", "how much"]):
            return "Starter is one ninety-nine a month for two thousand minutes. And no, we don't build websites. We focus on real-time voice."
        if "website" in lower:
            return "No, we don't build websites. We focus purely on real-time conversational voice."
        if any(w in lower for w in ["what do i need to do next", "recommend i do next", "what should i do next", "what would you recommend"]):
            return "I'd recommend a quick walkthrough where we test the voice agent on your actual workflow. We can set that up whenever you're ready."
        if any(w in lower for w in ["why should i choose you", "why choose you", "why lively"]):
            return "Teams pick us because the agent handles real-time interruptions naturally over Agora's network, so calls feel like talking to a person."
        if any(w in lower for w in ["expensive", "too much", "costly", "budget for this right now"]):
            return "Fair point. Is that compared to what you're spending now, or more about whether your call volume justifies it?"
        if any(w in lower for w in ["why would i replace", "salespeople already handle", "replace something that's working"]):
            return "If your current process works, I wouldn't replace it blindly. What's the one bottleneck your reps still run into?"
        if any(w in lower for w in ["prefer talking to real people", "hurt our business"]):
            return "Plenty of teams feel that way at first. The agent only handles first-touch qualification and hands buyers to your reps when they're ready."
        if any(w in lower for w in ["guarantee"]):
            return "We don't offer percentage guarantees, because results depend on your lead volume. A pilot on your own calls is the honest way to find out."
        if "hubspot" in lower:
            return "Yes, call notes, qualification details and booked meetings sync to HubSpot."
        if any(w in lower for w in ["build this myself", "just use chatgpt", "using chatgpt"]):
            return "You could, but reliable real-time voice with echo cancellation, barge-in and CRM hooks takes months to build. Lively gives you that out of the box."
        if any(w in lower for w in ["price", "cost", "how much", "pricing", "tier", "plan"]):
            return "Starter is one ninety-nine a month for two thousand minutes, and Growth is six ninety-nine for ten thousand minutes."
        if any(w in lower for w in ["who are you", "what do you guys do", "what is lively", "what do you do"]):
            return "We're Lively. We give teams real-time voice agents that sound human, handle interruptions and qualify inbound leads around the clock."
        if any(w in lower for w in ["hello", "hi there", "hey", "hi"]) and len(lower.split()) <= 4:
            return "Hey! Great to meet you. What brings you by today?"
        if any(w in lower for w in ["looking around", "just looking", "not interested"]):
            return "No problem at all, take your time. Let me know if you have any questions."

        # Otherwise, ask about the first qualification gap
        if state:
            for dimension, question in (
                ("need", "Got it. What's the biggest bottleneck your team is running into right now?"),
                ("budget", "Makes sense. Do you have a budget range in mind for this?"),
                ("authority", "Got it. Who else would be involved in deciding on this?"),
                ("timeline", "Understood. When would you want something like this live?"),
            ):
                if getattr(state.bant, dimension).get("status") != "Identified":
                    return question
        return "Sounds like a strong fit. Want to see it on your own workflow? I can set up a quick demo."

llm_router = LLMRouter()
