import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.llm_router import llm_router, latency_tracker
from app.models.schemas import DealState, ObjectionItem

def test_task5_2_routing_heuristic():
    state = DealState(channel_name="test_heuristics", session_id="sess_h")
    
    # Simple turn -> Groq (False for nvidia)
    assert not llm_router.should_route_to_nvidia("What are your pricing plans?", state)
    
    # Complex compliance / architecture query -> NVIDIA NIM (True)
    assert llm_router.should_route_to_nvidia("Do you support on-premise sovereign HIPAA compliance?", state)
    
    # High objection count -> NVIDIA NIM (True)
    state.active_objections.append(ObjectionItem(id="o1", category="pricing", utterance="Too expensive"))
    state.active_objections.append(ObjectionItem(id="o2", category="competitor", utterance="We use Twilio"))
    assert llm_router.should_route_to_nvidia("Tell me more about your architecture", state)
    print(" Task 5.2: Routing complexity heuristics verified!")

def test_task5_3_latency_instrumentation():
    # Record mock sample turns
    latency_tracker.record("groq:llama-3.3-70b-versatile", 120.5, 340.0)
    latency_tracker.record("groq:llama-3.3-70b-versatile", 145.0, 410.0)
    latency_tracker.record("nvidia:meta/llama-3.1-70b", 220.0, 780.0)
    latency_tracker.record("builtin-sales-brain", 35.0, 150.0)

    stats = latency_tracker.get_stats()
    assert stats["total_turns"] >= 4
    assert "ttft_p50_ms" in stats
    assert "ttft_p95_ms" in stats
    assert stats["ttft_p50_ms"] > 0
    assert stats["ttft_p95_ms"] >= stats["ttft_p50_ms"]
    print(f" Task 5.3: Latency budget analytics verified (p50: {stats['ttft_p50_ms']}ms, p95: {stats['ttft_p95_ms']}ms)!")

@pytest.mark.asyncio
async def test_task5_3_telemetry_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/telemetry/latency-stats")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert "ttft_p50_ms" in data["data"]
        print(" Task 5.3: GET /api/telemetry/latency-stats verified!")

@pytest.mark.asyncio
async def test_llm_stream_with_timing():
    state = DealState(channel_name="test_stream_timing", session_id="sess_t")
    chunks = []
    async for chunk in llm_router.stream_chat_completion(
        messages=[{"role": "user", "content": "How fast is Agora voice?"}],
        deal_state=state,
        channel_name="test_stream_timing"
    ):
        chunks.append(chunk)

    assert len(chunks) > 0
    stats = latency_tracker.get_stats()
    assert stats["total_turns"] > 0
    print(" Task 5.1 & 5.2: Stream generation with timing instrumentation verified!")

if __name__ == "__main__":
    test_task5_2_routing_heuristic()
    test_task5_3_latency_instrumentation()
    asyncio.run(test_task5_3_telemetry_endpoint())
    asyncio.run(test_llm_stream_with_timing())
    print("\n ALL PHASE 5 LLM ROUTER & LATENCY TESTS PASSED SUCCESSFULLY! ")
