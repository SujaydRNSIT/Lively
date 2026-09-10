import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from tests.helpers import new_session

@pytest.mark.asyncio
async def test_task3_1_rtc_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        channel, headers = await new_session(ac)
        r = await ac.post("/api/rtc-token", json={"channel_name": channel, "uid": 1001, "role": 1}, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["channel_name"] == channel
        assert len(data["token"]) > 10
        print(" Task 3.1: /api/rtc-token issued a token for the caller's own channel!")

@pytest.mark.asyncio
async def test_task3_2_start_agent_and_session_persistence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        channel, headers = await new_session(ac)
        r = await ac.post("/api/agent/start", json={"channel_name": channel, "customer_uid": 1001}, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert "agent_id" in data
        assert data["agent_rtc_uid"] == settings.AGORA_AGENT_RTC_UID
        assert "customer_token" in data
        print(f" Task 3.2: /api/agent/start launched agent: {data['agent_id']}!")

@pytest.mark.asyncio
async def test_task3_3_query_and_stop_agent():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        channel, headers = await new_session(ac)
        start_res = await ac.post("/api/agent/start", json={"channel_name": channel, "customer_uid": 2002}, headers=headers)
        agent_id = start_res.json()["agent_id"]

        q_res = await ac.get(f"/api/agent/status/{agent_id}", headers=headers)
        assert q_res.status_code == 200
        assert q_res.json()["status"] == "success"

        stop_res = await ac.post("/api/agent/stop", json={"agent_id": agent_id, "channel_name": channel}, headers=headers)
        assert stop_res.status_code == 200
        assert stop_res.json()["status"] == "success"
        print(f" Task 3.3: Query and Stop agent session {agent_id} verified!")

@pytest.mark.asyncio
async def test_task3_4_auth_protection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        channel, headers = await new_session(ac)
        _, other_headers = await new_session(ac)

        r_unauth = await ac.post("/api/agent/start", json={"channel_name": channel, "customer_uid": 1234})
        assert r_unauth.status_code == 401

        r_wrong = await ac.post("/api/agent/start", json={"channel_name": channel, "customer_uid": 1234}, headers=other_headers)
        assert r_wrong.status_code == 401

        r_auth = await ac.post("/api/agent/start", json={"channel_name": channel, "customer_uid": 1234}, headers=headers)
        assert r_auth.status_code == 200

        # DEBUG no longer bypasses auth
        orig_debug = settings.DEBUG
        settings.DEBUG = True
        try:
            assert (await ac.post("/api/agent/start", json={"channel_name": channel})).status_code == 401
        finally:
            settings.DEBUG = orig_debug
        print(" Task 3.4: Endpoint auth verified (401 without or with another visitor's session, 200 with your own)!")

if __name__ == "__main__":
    asyncio.run(test_task3_1_rtc_token())
    asyncio.run(test_task3_2_start_agent_and_session_persistence())
    asyncio.run(test_task3_3_query_and_stop_agent())
    asyncio.run(test_task3_4_auth_protection())
    print("\n ALL PHASE 3 AGORA RTC & AGENT SESSION TESTS PASSED SUCCESSFULLY! ")
