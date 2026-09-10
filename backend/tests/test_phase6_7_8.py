import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.schemas import DealStageEnum, ChatTurn
from app.core.deal_state_engine import deal_state_engine
from app.core.rag import rag_core
from app.scripts.ingest_docs import run_ingestion
from app.core.tools_impl.crm import crm_service
from app.core.tools_impl.calendar import calendar_service
from app.core.tools_impl.escalation import escalate_to_human
from app.core.tools_defs import execute_openai_tool_call
from tests.helpers import new_session

# ----------------- PHASE 6 TESTS -----------------
@pytest.mark.asyncio
async def test_phase6_deal_state_engine_change_log_and_persistence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        channel, headers = await new_session(ac)

        # 1. Initial State
        deal_state_engine.record_turn(channel, "buyer", "Hi, we are Acme Corp with 20 users looking for voice AI")
        state1 = deal_state_engine.get_state(channel)
        assert state1.users == 20
        assert state1.stage == DealStageEnum.DISCOVERY

        # 2. Additive Update: Scale changes from 20 -> 80
        deal_state_engine.record_turn(channel, "buyer", "Actually our team expanded to 80 users today and budget is $120k ARR")
        state2 = deal_state_engine.get_state(channel)
        assert state2.users == 80
        assert "$120K ARR" in state2.budget

        user_changes = [c for c in state2.change_log if c.field == "users"]
        assert len(user_changes) >= 2
        assert user_changes[-1].old_value == 20
        assert user_changes[-1].new_value == 80
        print(f" Phase 6: Deal State change log verified: {user_changes[-1].description}")

        # 3. GET /api/deal-state/{channel_name}
        res = await ac.get(f"/api/deal-state/{channel}", headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["users"] == 80
        assert len(data["change_log"]) > 0
    print(" Phase 6: GET /api/deal-state endpoint verified with change log!")

# ----------------- PHASE 7 TESTS -----------------
def test_phase7_rag_ingest_and_grounding():
    count = run_ingestion()
    assert count >= 6

    prod_hits = rag_core.retrieve("What is Agora SD-RTN network latency?")
    assert len(prod_hits) > 0
    assert any("SD-RTN" in h["content"] or "Agora" in h["content"] for h in prod_hits)

    pricing_hits = rag_core.retrieve("What are the pricing tiers?")
    assert len(pricing_hits) > 0
    assert any("$199" in h["content"] or "$699" in h["content"] for h in pricing_hits)

    context_str = rag_core.format_grounding_context("Tell me about OpenAI Realtime comparison")
    assert "OpenAI Realtime" in context_str

    # The knowledge base must not contradict the prompt's ban on invented statistics
    all_text = " ".join(d["content"] for d in rag_core.retrieve("pricing case study roi tco cost", top_k=10))
    assert "3.2x" not in all_text and "40% to 60%" not in all_text
    print(" Phase 7: RAG ingestion, retrieval, and grounding verified!")

# ----------------- PHASE 8 TESTS -----------------
@pytest.mark.asyncio
async def test_phase8_tools_and_execution_loop():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        channel, headers = await new_session(ac)
        state = deal_state_engine.get_or_create(channel)

        # 8.1 CRM Tool (create, update, log)
        crm_create = await crm_service.create_lead("Acme Robotics", "Elena Rostova", "elena@acme.com", "$75,000 ARR")
        assert crm_create["status"] == "success"
        crm_update = await crm_service.update_lead("Acme Robotics", "qualification", "$90,000 ARR", "Requested SOC2 report")
        assert crm_update["status"] == "success"
        assert crm_update["lead"]["deal_value"] == "$90,000 ARR"
        assert crm_update["lead"]["lead_id"] == crm_create["lead"]["lead_id"]  # stable ids

        # 8.2 Calendar Tool (check availability & book meeting)
        avail = await calendar_service.check_availability("tomorrow", "afternoon")
        assert avail["status"] == "success"
        assert len(avail["available_slots"]) > 0
        booked = await calendar_service.book_meeting("Tomorrow at 2:00 PM EST", "elena@acme.com", "Agora RTC Demo")
        assert booked["status"] == "CONFIRMED"
        again = await calendar_service.book_meeting("Tomorrow at 2:00 PM EST", "other@acme.com", "Agora RTC Demo")
        assert again["status"] == "UNAVAILABLE" and again["alternatives"]

        # 8.3 Escalation Tool with rich handoff (full Deal State + transcript)
        state.transcript.append(ChatTurn(role="buyer", content="I need custom enterprise SLA and HIPAA BAA signed"))
        esc_res = await escalate_to_human(channel, "VIP Buyer requested custom HIPAA SLA", "Immediate", state)
        assert esc_res["status"] == "HOT_TRANSFER_INITIATED"
        assert "bridge_url" in esc_res
        assert esc_res["transcript_count"] == 1

        # 8.4 OpenAI Tool Calling Loop Registry
        tool_res = await execute_openai_tool_call("book_meeting", {
            "time_slot": "Next Tuesday at 11:00 AM EST",
            "email": "director@enterprise.com"
        }, channel, state)
        assert tool_res["status"] == "CONFIRMED"
        assert state.stage == DealStageEnum.DEMO_SCHEDULING

        # 8.5 POST /api/tools/send-meeting-invite (re-sends the booked demo's invite)
        res = await ac.post("/api/tools/send-meeting-invite", json={
            "channel_name": channel,
            "email": "lead@enterprise.com",
        }, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        data = res.json()["data"]
        assert data["status"] == "CONFIRMED"
        assert data["email"] == "lead@enterprise.com"
    print(" Phase 8: CRM, Calendar, Rich Escalation Handoff, and Tool-Calling Loop verified!")

if __name__ == "__main__":
    asyncio.run(test_phase6_deal_state_engine_change_log_and_persistence())
    test_phase7_rag_ingest_and_grounding()
    asyncio.run(test_phase8_tools_and_execution_loop())
    print("\n ALL PHASE 6, 7 & 8 TESTS PASSED SUCCESSFULLY! ")
