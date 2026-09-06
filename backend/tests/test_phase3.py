import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings

@pytest.mark.asyncio
async def test_task3_1_rtc_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/rtc-token", json={
            "channel_name": "sales_channel_alpha",
            "uid": 1001,
            "role": 1
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["channel_name"] == "sales_channel_alpha"
        assert "token" in data
        assert len(data["token"]) > 10
        print(" Task 3.1: /api/rtc-token successfully generated Agora RTC Token!")

@pytest.mark.asyncio
async def test_task3_2_start_agent_and_session_persistence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/agent/start", json={
            "channel_name": "sales_channel_alpha",
            "customer_uid": 1001
        }, headers={"X-Lively-Key": settings.LIVELY_API_KEY})

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert "agent_id" in data
        assert data["agent_rtc_uid"] == settings.AGORA_AGENT_RTC_UID
        assert "customer_token" in data
        print(f" Task 3.2: /api/agent/start successfully launched agent: {data['agent_id']}!")
        return data["agent_id"]

@pytest.mark.asyncio
async def test_task3_3_query_and_stop_agent():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Start
        start_res = await ac.post("/api/agent/start", json={
            "channel_name": "channel_to_stop",
            "customer_uid": 2002
        }, headers={"X-Lively-Key": settings.LIVELY_API_KEY})
        agent_id = start_res.json()["agent_id"]

        # Query Status
        q_res = await ac.get(f"/api/agent/status/{agent_id}", headers={"X-Lively-Key": settings.LIVELY_API_KEY})
        assert q_res.status_code == 200
        assert q_res.json()["status"] == "success"

        # Stop Agent
        stop_res = await ac.post("/api/agent/stop", json={
            "agent_id": agent_id,
            "channel_name": "channel_to_stop"
        }, headers={"X-Lively-Key": settings.LIVELY_API_KEY})
        assert stop_res.status_code == 200
        assert stop_res.json()["status"] == "success"
        print(f" Task 3.3: Query and Stop agent session {agent_id} verified!")

@pytest.mark.asyncio
async def test_task3_4_auth_protection():
    transport = ASGITransport(app=app)
    # Temporarily force DEBUG = False to verify security barrier
    orig_debug = settings.DEBUG
    settings.DEBUG = False
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Missing key -> 401 Unauthorized
            r_unauth = await ac.post("/api/agent/start", json={"channel_name": "secret_room", "customer_uid": 1234})
            assert r_unauth.status_code == 401
            assert "Unauthorized" in r_unauth.json()["detail"]

            # Valid key -> 200 OK
            r_auth = await ac.post("/api/agent/start", json={
                "channel_name": "secret_room",
                "customer_uid": 1234
            }, headers={"X-Lively-Key": settings.LIVELY_API_KEY})
            assert r_auth.status_code == 200
            print(" Task 3.4: Endpoint Auth protection verified (401 on unauthorized, 200 on authorized)!")
    finally:
        settings.DEBUG = orig_debug

if __name__ == "__main__":
    asyncio.run(test_task3_1_rtc_token())
    asyncio.run(test_task3_2_start_agent_and_session_persistence())
    asyncio.run(test_task3_3_query_and_stop_agent())
    asyncio.run(test_task3_4_auth_protection())
    print("\n ALL PHASE 3 AGORA RTC & AGENT SESSION TESTS PASSED SUCCESSFULLY! ")
