import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.deal_state_engine import deal_state_engine
from app.services.email_service import email_service, parse_slot_to_datetimes, build_google_calendar_url

@pytest.mark.asyncio
async def test_email_service_slot_parsing_and_calendar():
    start_dt, end_dt = parse_slot_to_datetimes("Thursday at 2:00 PM EST")
    assert start_dt < end_dt
    assert (end_dt - start_dt).total_seconds() == 1800  # 30 mins

    gcal_url = build_google_calendar_url(
        "Lively Voice AI Demo",
        start_dt,
        end_dt,
        "Meeting details",
        "https://meet.google.com/new"
    )
    assert "https://calendar.google.com/calendar/render" in gcal_url
    assert "dates=" in gcal_url
    assert "location=https%3A//meet.google.com/new" in gcal_url

@pytest.mark.asyncio
async def test_set_contact_endpoint_and_state():
    channel = "test_contact_channel_99"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(f"/api/deal-state/{channel}/set-contact", json={
            "email": "sarah.connor@cyberdyne.ai",
            "name": "Sarah Connor",
            "company": "Cyberdyne Systems"
        })
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["contact_email"] == "sarah.connor@cyberdyne.ai"
        assert data["contact_name"] == "Sarah Connor"
        assert data["company"] == "Cyberdyne Systems"

        # Now verify that when a demo is booked, it uses this contact email automatically
        demo_res = await ac.post("/api/tools/book-demo", json={
            "channel_name": channel,
            "time_slot": "Thursday at 2:00 PM EST"
        })
        assert demo_res.status_code == 200
        demo_data = demo_res.json()["data"]
        assert demo_data["email"] == "sarah.connor@cyberdyne.ai"
        assert "google_calendar_link" in demo_data
        assert "dates=" in demo_data["google_calendar_link"]
