import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.deal_state_engine import deal_state_engine
from app.services.email_service import parse_slot_to_datetimes, build_google_calendar_url
from tests.helpers import new_session

@pytest.mark.asyncio
async def test_email_service_slot_parsing_and_calendar():
    start_dt, end_dt = parse_slot_to_datetimes("Thursday at 2:00 PM EST")
    assert start_dt < end_dt
    assert (end_dt - start_dt).total_seconds() == 1800  # 30 mins
    assert start_dt.hour == 19  # 2 PM EST is 19:00 UTC

    labelled, _ = parse_slot_to_datetimes("Monday Sep 14 at 10:00 AM EST")
    assert (labelled.month, labelled.day, labelled.hour) == (9, 14, 15)

    gcal_url = build_google_calendar_url("Lively Voice AI Demo", start_dt, end_dt, "Meeting details", "https://meet.jit.si/Lively-x")
    assert "https://calendar.google.com/calendar/render" in gcal_url
    assert "dates=" in gcal_url

@pytest.mark.asyncio
async def test_set_contact_endpoint_and_state():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        channel, headers = await new_session(ac)
        res = await ac.post(f"/api/deal-state/{channel}/set-contact", json={
            "email": "sarah.connor@cyberdyne.ai",
            "name": "Sarah Connor",
            "company": "Cyberdyne Systems"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["contact_email"] == "sarah.connor@cyberdyne.ai"
        assert data["contact_name"] == "Sarah Connor"
        assert data["company"] == "Cyberdyne Systems"

        # A demo booked afterwards uses this contact email automatically
        demo_res = await ac.post("/api/tools/book-demo", json={"channel_name": channel, "time_slot": "Thursday at 2:00 PM EST"}, headers=headers)
        assert demo_res.status_code == 200
        demo_data = demo_res.json()["data"]
        assert demo_data["email"] == "sarah.connor@cyberdyne.ai"
        assert "dates=" in demo_data["google_calendar_link"]

        bad = await ac.post(f"/api/deal-state/{channel}/set-contact", json={"email": "not-an-email"}, headers=headers)
        assert bad.status_code == 400

def test_booking_without_email_waits_for_an_address():
    channel = "test_booking_without_email"
    state = deal_state_engine.record_turn(channel, "buyer", "Can we schedule a demo for tomorrow at 2 PM?")
    assert state.scheduled_demo is not None
    assert state.scheduled_demo["email"] is None
    assert state.scheduled_demo["invite_status"] == "pending_email"
    assert "Tomorrow" in state.scheduled_demo["time"]
    assert "2:00 PM" in state.scheduled_demo["time"]
    assert any("need email for invite" in note for note in state.action_items)
    assert "email" in state.next_best_action.lower()

def test_spoken_email_updates_contact_and_demo():
    channel = "test_spoken_email_channel"
    deal_state_engine.record_turn(channel, "buyer", "Please schedule a demo for Friday at 3 PM")
    state = deal_state_engine.record_turn(channel, "buyer", "My email address is buyer@example.com")
    assert state.contact_email == "buyer@example.com"
    assert state.scheduled_demo["email"] == "buyer@example.com"
    assert state.scheduled_demo["invite_status"] in ("preview_only", "delivered")

def test_spoken_email_from_speech_to_text():
    channel = "test_spoken_email_words"
    state = deal_state_engine.record_turn(channel, "buyer", "Sure, my email is jane dot doe at acme dot com")
    assert state.contact_email is None  # "jane dot doe" isn't a local part we can trust
    state = deal_state_engine.record_turn(channel, "buyer", "My email is jane at acme dot com")
    assert state.contact_email == "jane@acme.com"
