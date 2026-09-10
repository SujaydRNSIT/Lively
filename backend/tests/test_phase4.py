import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.deal_state_engine import deal_state_engine
from tests.helpers import new_session

@pytest.mark.asyncio
async def test_task4_1_openai_chat_completions_sse():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        _, headers = await new_session(ac)
        req = {
            "model": "lively-sales-brain",
            "messages": [{"role": "user", "content": "How does Agora compare to OpenAI Realtime?"}],
            "stream": True
        }
        res = await ac.post("/v1/chat/completions", json=req, headers=headers)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        chunks = [line for line in res.text.split("\n\n") if line.startswith("data:")]
        assert len(chunks) > 0
        assert any("chat.completion.chunk" in c for c in chunks)
        print(f" Task 4.1: /v1/chat/completions streamed {len(chunks)} SSE chunks successfully!")

@pytest.mark.asyncio
async def test_task4_1_custom_metadata_first_chunk():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        _, headers = await new_session(ac)
        req = {
            "model": "lively-sales-brain",
            "messages": [{"role": "user", "content": "Can you check calendar and schedule a demo?"}],
            "stream": True
        }
        res = await ac.post("/v1/chat/completions", json=req, headers=headers)
        assert res.status_code == 200

        body_text = res.text
        assert "chat.completion.custom_metadata" in body_text
        assert "interruptable" in body_text
        print(" Task 4.1: chat.completion.custom_metadata first chunk emitted!")

@pytest.mark.asyncio
async def test_task4_2_additive_mergeable_deal_state():
    channel = "test_additive_channel"

    deal_state_engine.record_turn(channel, "buyer", "We have 50 users and need deployment in Q1")
    state1 = deal_state_engine.get_state(channel)
    assert "50 seats" in state1.bant.need.get("scale", "")
    assert "Q1" in state1.bant.timeline.get("timeframe", "")

    deal_state_engine.record_turn(channel, "buyer", "Actually we have 80 users now and our budget is $80k ARR")
    state2 = deal_state_engine.get_state(channel)
    assert "80 seats" in state2.bant.need.get("scale", "")
    assert "$80K ARR" in state2.bant.budget.get("value", "")
    assert "Q1" in state2.bant.timeline.get("timeframe", "")  # preserved!

    deal_state_engine.record_turn(channel, "buyer", "I am the VP of Product and I make the final call")
    state3 = deal_state_engine.get_state(channel)
    assert "Product" in state3.bant.authority.get("role", "")
    assert state3.bant.authority.get("decision_maker") is True
    assert "$80K ARR" in state3.bant.budget.get("value", "")  # preserved!
    assert "80 seats" in state3.bant.need.get("scale", "")  # preserved!

    print(" Task 4.2: Additive and mergeable Deal State verified across multiple turns!")

if __name__ == "__main__":
    asyncio.run(test_task4_1_openai_chat_completions_sse())
    asyncio.run(test_task4_1_custom_metadata_first_chunk())
    asyncio.run(test_task4_2_additive_mergeable_deal_state())
    print("\n ALL PHASE 4 CUSTOM LLM ENDPOINT TESTS PASSED SUCCESSFULLY! ")
