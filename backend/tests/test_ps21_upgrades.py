"""
Regression tests for the PS21 upgrades: qualification, objections (incl. trust), availability,
escalation with context, CRM activity, auth/isolation, honest telemetry and non-blocking email.
"""
import asyncio
import json
import smtplib
import time

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import settings, Settings
from app.models.schemas import DealState, DealStageEnum
from app.core.deal_state_engine import deal_state_engine
from app.core.understanding import extract_authority, extract_timeline, extract_user_count, words_to_int, llm_understanding
from app.core.llm_router import llm_router, latency_tracker, LatencyTracker, normalize_spoken_numbers, SpokenStream
from app.core.tools_impl.crm import crm_service
from app.core.tools_impl.escalation import escalation_service
from app.core.background import drain
from tests.helpers import new_session


# ------------------------------------------------------------------ configuration

def test_no_hardcoded_credentials_or_debug_defaults():
    fields = Settings.model_fields
    assert fields["SMTP_USER"].default is None
    assert fields["SMTP_PASSWORD"].default is None
    assert fields["NVIDIA_NIM_API_KEY"].default == ""
    assert fields["LIVELY_LLM_SHARED_SECRET"].default == ""
    assert fields["DEBUG"].default is False
    assert fields["AGENT_RESPONSE_DELAY_SECONDS"].default == 0.0
    assert "*" not in fields["CORS_ALLOWED_ORIGINS"].default


# ------------------------------------------------------------------ understanding (rules)

def test_negated_booking_is_a_decline():
    state = deal_state_engine.record_turn("ps21_neg", "buyer", "No, I do not want to book a meeting right now.")
    assert state.scheduled_demo is None
    assert state.last_understanding["demo_request"] == "decline"

def test_authority_negation_and_reporting_line():
    assert extract_authority("i'm not the ceo, i just report to the head of sales.") == ("Reports to Head of Sales", False)
    assert extract_authority("i'm the vp of product and i make the final call") == ("VP of Product", True)

def test_timeline_ignores_history_and_keeps_plans():
    assert extract_timeline("Honestly our Q3 was rough, I'm just browsing.") is None
    assert extract_timeline("We want to go live by Q1") == "by Q1"
    assert extract_timeline("Can we meet next week for a demo?") is None

def test_seat_counts_prefer_seats_and_spoken_numbers():
    assert extract_user_count("we lost 3 reps last month, so maybe 5 seats") == 5
    assert extract_user_count("we're now eighty users") == 80
    assert words_to_int("one hundred and twenty") == 120


# ------------------------------------------------------------------ qualification

def test_qualification_starts_unknown_and_completes():
    channel = "ps21_qual"
    state = deal_state_engine.get_or_create(channel)
    assert state.qualification_score == 0 and not state.lead_qualified
    assert state.bant.authority["status"] == "Unknown" and state.budget is None and state.users is None

    deal_state_engine.record_turn(channel, "buyer", "Actually our sales team just expanded to 80 users and our budget is $100k ARR.")
    assert state.qualification_score == 25 and state.stage == DealStageEnum.DISCOVERY

    deal_state_engine.record_turn(channel, "buyer", "I'm the VP of Product, and we need to respond to inbound leads faster.")
    assert state.qualification_score == 75 and state.stage == DealStageEnum.QUALIFICATION

    deal_state_engine.record_turn(channel, "buyer", "We want to go live by Q1.")
    assert state.lead_qualified and state.qualification_score == 100
    assert state.crm_lead.status == "Qualified"
    assert any(e.field == "qualification" for e in state.change_log)


# ------------------------------------------------------------------ objections

def test_trust_objection_detected_and_resolved_on_acceptance():
    channel = "ps21_trust"
    state = deal_state_engine.record_turn(channel, "buyer", "How do I know it won't make things up to my customers?")
    assert [o.type for o in state.active_objections] == ["trust"]
    assert state.stage == DealStageEnum.OBJECTION_HANDLING
    deal_state_engine.record_turn(channel, "agent", "It only answers from your approved docs, and anything uncertain goes to a human rep.")
    state = deal_state_engine.record_turn(channel, "buyer", "Okay, that makes sense.")
    assert state.active_objections == []
    assert state.resolved_objections[0].resolution == "accepted"

def test_pricing_question_is_not_an_objection_but_pushback_is():
    state = deal_state_engine.record_turn("ps21_price", "buyer", "How much does Lively cost?")
    assert state.active_objections == []
    state = deal_state_engine.record_turn("ps21_price", "buyer", "Hmm, $699 a month seems expensive.")
    assert [o.type for o in state.active_objections] == ["pricing"]
    assert state.budget is None  # a price reaction is not the buyer's budget

def test_objection_closes_when_buyer_moves_on():
    channel = "ps21_moveon"
    deal_state_engine.record_turn(channel, "buyer", "We already use Twilio.")
    deal_state_engine.record_turn(channel, "buyer", "We have 40 users.")
    state = deal_state_engine.record_turn(channel, "buyer", "What integrations do you support?")
    assert state.active_objections == []
    assert state.resolved_objections[0].resolution == "moved_on"


# ------------------------------------------------------------------ availability

def test_unavailable_slot_offers_alternatives_then_books_the_choice(monkeypatch):
    monkeypatch.setattr(settings, "CALENDAR_WORKING_DAYS", "mon,tue,wed,thu,fri")
    channel = "ps21_slot"
    state = deal_state_engine.record_turn(channel, "buyer", "Can we book a demo on Saturday at 2 PM?")
    assert state.scheduled_demo is None
    assert "Saturday" in state.slot_conflict["reason"]
    alternatives = state.slot_conflict["alternatives"]
    assert len(alternatives) == 3
    assert not any(day in a for a in alternatives for day in ("Saturday", "Sunday"))
    assert "unavailable" in state.next_best_action

    state = deal_state_engine.record_turn(channel, "buyer", "The first one works.")
    assert state.scheduled_demo["time"].startswith(alternatives[0])
    assert state.slot_conflict is None

def test_same_slot_cannot_be_double_booked_and_links_are_real_rooms():
    first = deal_state_engine.record_turn("ps21_a", "buyer", "Can we schedule a demo next Tuesday at 2 PM?")
    link = first.scheduled_demo["meeting_link"]
    assert link.startswith(settings.MEETING_ROOM_BASE_URL) and "meet.google.com/new" not in link

    second = deal_state_engine.record_turn("ps21_b", "buyer", "Can we schedule a demo next Tuesday at 2 PM?")
    assert second.scheduled_demo is None
    assert second.slot_conflict["reason"] == "that slot is already booked"
    assert second.slot_conflict["alternatives"]

def test_demo_request_without_time_offers_slots_instead_of_inventing_one():
    state = deal_state_engine.record_turn("ps21_notime", "buyer", "We'd like to book an enterprise demo.")
    assert state.scheduled_demo is None and state.pending_demo_request
    assert state.available_slots and "Offer open demo slots" in state.next_best_action

def test_cancel_releases_the_slot():
    deal_state_engine.record_turn("ps21_cancel", "buyer", "Book a demo for next Wednesday at 10 AM.")
    state = deal_state_engine.record_turn("ps21_cancel", "buyer", "Actually, please cancel the demo.")
    assert state.scheduled_demo is None
    other = deal_state_engine.record_turn("ps21_cancel2", "buyer", "Book a demo for next Wednesday at 10 AM.")
    assert other.scheduled_demo is not None


# ------------------------------------------------------------------ escalation

def test_voice_escalation_carries_context():
    channel = "ps21_handoff"
    deal_state_engine.record_turn(channel, "buyer", "We have 80 users and our budget is $100k ARR.")
    deal_state_engine.record_turn(channel, "agent", "Got it. Growth fits that volume.")
    state = deal_state_engine.record_turn(channel, "buyer", "Our legal team needs custom contract terms. Can I talk to a real person?")
    assert state.stage == DealStageEnum.ESCALATED
    handoff = state.escalation
    assert handoff["trigger"] == "buyer_request"
    assert handoff["summary"]["seats"] == 80 and handoff["summary"]["budget"] == "$100K ARR"
    assert handoff["transcript_count"] == 3 and handoff["recent_turns"][-1]["role"] == "buyer"
    assert handoff["bridge_url"].startswith(settings.MEETING_ROOM_BASE_URL)
    queued = next(r for r in escalation_service.queue() if r["id"] == handoff["id"])
    assert len(queued["transcript"]) == 3

def test_repeated_frustration_escalates():
    channel = "ps21_frustrated"
    deal_state_engine.record_turn(channel, "buyer", "This is frustrating, I've talked to three people already.")
    state = deal_state_engine.record_turn(channel, "buyer", "Honestly this is a waste of my time.")
    assert state.escalation and state.escalation["trigger"] == "frustration"

def test_ps21_example_scenario_does_not_escalate_early():
    channel = "ps21_example"
    for text in ["How much does Lively cost?", "Wait, how do you compare to OpenAI Realtime and Twilio?", "It seems expensive compared to Twilio."]:
        state = deal_state_engine.record_turn(channel, "buyer", text)
    assert state.escalation is None

@pytest.mark.asyncio
async def test_rest_escalation_uses_the_real_channel_state():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        channel, headers = await new_session(ac)
        deal_state_engine.record_turn(channel, "buyer", "We need to cut response times for inbound leads.")
        res = await ac.post("/api/tools/escalate", json={"channel_name": channel, "reason": "VIP asked for an AE"}, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["summary"]["need"] == ["cut response times for inbound leads"]
        assert data["transcript_count"] == 1
        assert deal_state_engine.get_state(channel).stage == DealStageEnum.ESCALATED


# ------------------------------------------------------------------ CRM

def test_crm_lead_and_activity_follow_the_conversation():
    state = deal_state_engine.record_turn("ps21_crm", "buyer", "We have 25 users and our budget is $30k a year.")
    assert state.crm_lead.lead_id and state.crm_lead.lead_id.startswith("lead_")
    types = [a["type"] for a in state.crm_activity]
    assert "users" in types and "budget" in types
    record = crm_service.get_lead(state.crm_lead.lead_id)
    assert record["seats"] == 25 and record["deal_value"].startswith("$30K")


# ------------------------------------------------------------------ auth & isolation

@pytest.mark.asyncio
async def test_endpoints_require_a_session_for_that_channel():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        a_channel, a_headers = await new_session(ac)
        _, b_headers = await new_session(ac)
        chat = {"messages": [{"role": "user", "content": "hi"}]}

        assert (await ac.get(f"/api/deal-state/{a_channel}")).status_code == 401
        assert (await ac.get(f"/api/deal-state/{a_channel}", headers=b_headers)).status_code == 401
        assert (await ac.get(f"/api/deal-state/{a_channel}", headers=a_headers)).status_code == 200
        assert (await ac.post("/api/tools/send-meeting-invite", json={"channel_name": a_channel, "email": "x@example.com"})).status_code == 401
        assert (await ac.post("/api/rtc-token", json={"channel_name": a_channel, "uid": 5})).status_code == 401
        assert (await ac.post(f"/v1/chat/completions?channel={a_channel}", json=chat)).status_code == 401
        assert (await ac.post(f"/v1/chat/completions?channel={a_channel}", json=chat, headers=b_headers)).status_code == 403
        agora = {"Authorization": f"Bearer {settings.LIVELY_LLM_SHARED_SECRET}"}
        assert (await ac.post(f"/v1/chat/completions?channel={a_channel}", json=chat, headers=agora)).status_code == 200
        wrong = {"Authorization": "Bearer not-the-secret"}
        assert (await ac.post(f"/v1/chat/completions?channel={a_channel}", json=chat, headers=wrong)).status_code == 401

@pytest.mark.asyncio
async def test_resuming_a_session_keeps_the_channel_and_forgery_fails():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        first = (await ac.post("/api/session", json={})).json()
        resumed = (await ac.post("/api/session", json={"resume_token": first["session_token"]})).json()
        assert resumed["channel_name"] == first["channel_name"] and resumed["resumed"] is True
        token = first["session_token"]
        forged = token[:10] + ("A" if token[10] != "A" else "B") + token[11:]
        fresh = (await ac.post("/api/session", json={"resume_token": forged})).json()
        assert fresh["resumed"] is False and fresh["channel_name"] != first["channel_name"]

def test_websocket_requires_the_session_token():
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    with TestClient(app) as client:
        data = client.post("/api/session", json={}).json()
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/api/ws/telemetry/{data['channel_name']}") as ws:
                ws.receive_text()
        with client.websocket_connect(f"/api/ws/telemetry/{data['channel_name']}?token={data['session_token']}") as ws:
            assert json.loads(ws.receive_text())["type"] == "DEAL_STATE_SNAPSHOT"


# ------------------------------------------------------------------ email stays off the voice path

@pytest.mark.asyncio
async def test_slow_smtp_does_not_block_other_requests(monkeypatch):
    class SlowSMTP:
        def __init__(self, *a, **k):
            time.sleep(1.5)
        def starttls(self, *a, **k): pass
        def login(self, *a, **k): pass
        def sendmail(self, *a, **k): pass
        def quit(self): pass

    monkeypatch.setattr(smtplib, "SMTP", SlowSMTP)
    monkeypatch.setattr(settings, "SMTP_USER", "bot@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "x")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t", timeout=30) as ac:
        channel, headers = await new_session(ac)
        t0 = time.perf_counter()

        async def booking():
            await asyncio.sleep(0.05)
            await ac.post("/v1/chat/completions", headers=headers, json={"messages": [
                {"role": "user", "content": "Can we schedule a demo next Thursday at 2 PM? me@example.com"}]})
            return time.perf_counter() - t0

        async def health():
            await asyncio.sleep(0.2)
            await ac.get("/health")
            return (time.perf_counter() - (t0 + 0.2)) * 1000

        booking_seconds, health_late_ms = await asyncio.gather(booking(), health())
        assert health_late_ms < 500
        assert booking_seconds < 1.0
        await drain(5)
        assert deal_state_engine.get_state(channel).scheduled_demo["invite_status"] == "delivered"


# ------------------------------------------------------------------ LLM router

def _fake_client(tokens, fail_after=None, first_byte_delay=0.0, fail_create=0):
    calls = {"create": 0}

    class Delta:
        def __init__(self, content): self.content = content

    class Choice:
        def __init__(self, content): self.delta = Delta(content)

    class Chunk:
        def __init__(self, content): self.choices = [Choice(content)]

    class Stream:
        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            for i, token in enumerate(tokens):
                if fail_after is not None and i == fail_after:
                    raise RuntimeError("connection reset mid-stream")
                yield Chunk(token)

    class Completions:
        async def create(self, **kwargs):
            calls["create"] += 1
            if calls["create"] <= fail_create:
                raise RuntimeError("503 upstream")
            await asyncio.sleep(first_byte_delay)
            return Stream()

    client = type("Client", (), {})()
    client.chat = type("Chat", (), {})()
    client.chat.completions = Completions()
    return client, calls

def _spoken(chunks):
    roles, text = 0, []
    for chunk in chunks:
        if chunk.startswith("data: {"):
            delta = json.loads(chunk[6:])["choices"][0]["delta"]
            roles += 1 if delta.get("role") else 0
            text.append(delta.get("content") or "")
    return roles, "".join(text)

@pytest.mark.asyncio
async def test_ttft_is_measured_at_the_first_real_token(monkeypatch):
    client, _ = _fake_client(["Hello ", "there. "], first_byte_delay=0.3)
    monkeypatch.setattr(llm_router, "groq_client", client)
    monkeypatch.setattr(llm_router, "nvidia_client", None)
    state = DealState(channel_name="ps21_ttft", session_id="s")
    [c async for c in llm_router.stream_chat_completion([{"role": "user", "content": "hi"}], state, "ps21_ttft")]
    assert latency_tracker.ttft_records[-1] >= 300

@pytest.mark.asyncio
async def test_mid_stream_failure_does_not_restart_the_answer(monkeypatch):
    groq, _ = _fake_client(["Our Starter ", "plan is ", "X ", "Y "], fail_after=2)
    nim, nim_calls = _fake_client(["Starter is one ninety-nine. "])
    monkeypatch.setattr(llm_router, "groq_client", groq)
    monkeypatch.setattr(llm_router, "nvidia_client", nim)
    state = DealState(channel_name="ps21_mid", session_id="s")
    chunks = [c async for c in llm_router.stream_chat_completion([{"role": "user", "content": "price?"}], state, "ps21_mid")]
    roles, text = _spoken(chunks)
    assert roles == 1 and text == "Our Starter plan is " and nim_calls["create"] == 0

@pytest.mark.asyncio
async def test_failure_before_first_token_retries_then_falls_back(monkeypatch):
    groq, groq_calls = _fake_client(["never"], fail_create=5)
    nim, _ = _fake_client(["Starter is one ninety-nine. "])
    monkeypatch.setattr(llm_router, "groq_client", groq)
    monkeypatch.setattr(llm_router, "nvidia_client", nim)
    state = DealState(channel_name="ps21_pre", session_id="s")
    chunks = [c async for c in llm_router.stream_chat_completion([{"role": "user", "content": "price?"}], state, "ps21_pre")]
    assert groq_calls["create"] == 2  # retried once
    assert _spoken(chunks)[1] == "Starter is one ninety-nine. "

def test_spoken_numbers_leave_times_and_amounts_alone():
    untouched = "Tomorrow at 2:30 PM or 10:00 AM, we support 10,000 minutes for $30."
    assert normalize_spoken_numbers(untouched) == untouched
    assert normalize_spoken_numbers("a 30-minute demo, about 30 mins") == "a thirty-minute demo, about thirty mins"
    stream = SpokenStream()
    assert stream.feed("a 3") + stream.feed("0-minute demo ") + stream.flush() == "a thirty-minute demo "

def test_latency_stats_are_null_until_measured():
    stats = LatencyTracker().get_stats()
    assert stats["measured"] is False and stats["ttft_p50_ms"] is None and stats["total_turns"] == 0


# ------------------------------------------------------------------ LLM understanding path

@pytest.mark.asyncio
async def test_llm_understanding_is_used_and_times_out_gracefully(monkeypatch):
    payload = {"intent": "request_demo", "demo_request": "decline", "user_count": 80, "role": "vp of sales",
               "is_decision_maker": True, "sentiment": "skeptical",
               "objections": [{"type": "trust", "summary": "worried about wrong answers"}]}

    class Completions:
        def __init__(self, delay): self.delay = delay
        async def create(self, **kwargs):
            await asyncio.sleep(self.delay)
            message = type("Message", (), {"content": json.dumps(payload)})
            return type("Response", (), {"choices": [type("Choice", (), {"message": message})()]})()

    fake = type("Client", (), {})()
    fake.chat = type("Chat", (), {})()
    fake.chat.completions = Completions(0.0)
    monkeypatch.setattr(llm_understanding, "client", fake)

    channel = "ps21_llm"
    text = "Book it... actually no, not yet. We're eighty people and I worry it'll give wrong answers."
    understanding = await llm_understanding.extract(text, deal_state_engine.get_or_create(channel))
    assert understanding["source"] == "llm" and understanding["demo_request"] == "decline"
    assert understanding["role"] == "VP of Sales" and understanding["sentiment"] == "Skeptical"

    state = deal_state_engine.record_turn(channel, "buyer", text, understanding=understanding)
    assert state.scheduled_demo is None and state.users == 80
    assert [o.type for o in state.active_objections] == ["trust"]

    fake.chat.completions = Completions(settings.EXTRACTION_TIMEOUT_SECONDS + 0.3)
    assert await llm_understanding.extract("hello", state) is None
