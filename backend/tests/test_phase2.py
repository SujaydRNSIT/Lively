import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.models.schemas import DealState, Lead, BANTStatus
from app.core.deal_state_engine import deal_state_engine
from app.core.rag import rag_core
from app.core.decision import decision_engine
from app.core.tools_impl.crm import sync_crm_deal
from app.core.tools_impl.calendar import book_calendar_slot
from app.core.tools_impl.escalation import trigger_human_escalation

def test_config():
    assert settings.PROJECT_NAME is not None
    assert settings.PORT == 8000
    print(" Config loading passed!")

def test_schemas():
    state = DealState(channel_name="test-channel", session_id="test-session")
    assert str(state.stage).lower() in ("discovery", "dealstageenum.discovery")
    assert state.crm_lead.company is not None
    print(" Schemas validation passed!")

def test_rag_and_decision():
    hits = rag_core.retrieve("What are your pricing plans?")
    assert len(hits) > 0
    assert "pricing" in hits[0]["category"]

    state = deal_state_engine.get_or_create("decision_channel")
    next_action = decision_engine.evaluate_next_action(state)
    assert len(next_action) > 0
    print(" RAG & Decision Engine passed!")

@pytest.mark.asyncio
async def test_tools():
    crm_res = await sync_crm_deal("Enterprise AI Corp", "Qualified", "$100,000 ARR")
    assert crm_res["status"] == "success"

    cal_res = await book_calendar_slot("Friday 2pm EST", "buyer@acme.com")
    assert cal_res["status"] == "CONFIRMED"

    esc_res = await trigger_human_escalation("Custom contract review")
    assert esc_res["status"] == "HOT_TRANSFER_INITIATED"
    print(" Tool implementations (CRM, Calendar, Escalation) passed!")

@pytest.mark.asyncio
async def test_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Root & Health
        r = await ac.get("/health")
        assert r.status_code == 200

        # RTC Token
        r = await ac.post("/api/agora/token", json={"channel_name": "room1", "uid": 1001})
        assert r.status_code == 200
        assert "token" in r.json()

        # Deal State
        r = await ac.get("/api/deal-state/room1")
        assert r.status_code == 200
        assert r.json()["data"]["channel_name"] == "room1"

        # Tools Webhooks
        r = await ac.post("/api/tools/book-demo", json={
            "channel_name": "room1",
            "time_slot": "Next Monday 10am",
            "email": "lead@test.com"
        })
        assert r.status_code == 200

        # OpenAI Chat Completions Proxy
        r = await ac.post("/v1/chat/completions?channel=room1", json={
            "messages": [{"role": "user", "content": "How much does Lively cost?"}],
            "stream": True
        })
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]

    print(" All API Endpoints & LLM Proxy verified!")

if __name__ == "__main__":
    test_config()
    test_schemas()
    test_rag_and_decision()
    asyncio.run(test_tools())
    asyncio.run(test_api_endpoints())
    print("\n PHASE 2 BACKEND TEST SUITE COMPLETED SUCCESSFULLY! ")
