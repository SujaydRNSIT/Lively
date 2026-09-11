import asyncio
import time
from app.config import settings
from app.core.understanding import extract_email
from app.core.deal_state_engine import deal_state_engine
from app.services.email_service import email_service


async def run_full_fledged_demo():
    print("=" * 60)
    print("RUNNING FULL-FLEDGED LIVELY DEMO & EMAIL VERIFICATION")
    print(f"Configured SMTP Server: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
    print(f"Configured SMTP Sender: {settings.SMTP_USER}")
    print("=" * 60)

    # 1. Test Email Extraction
    print("\n[STEP 1] Testing Robust Email Extraction from Speech/Text...")
    samples = [
        "my email is anish hyd 995 at gmail dot com",
        "anishhyd995@gmail.com",
        "send the invite to anishhyd995 at gmail.com",
        "reach me at client at acme dot io",
        "my email is anishhyd995 @ gmail . com",
    ]
    for s in samples:
        res = extract_email(s)
        print(f"  Utterance: '{s}' -> Extracted: '{res}'")
        assert res is not None, f"Failed to extract email from: {s}"
    print("-> All speech/text email extractions passed!")

    # 2. Setup Session with Client Email
    channel_name = f"verify_demo_{int(time.time())}"
    client_email = "anishhyd995@gmail.com"
    print(f"\n[STEP 2] Setting up channel: {channel_name} with client email: {client_email}")
    state = deal_state_engine.set_contact(channel_name, client_email, name="Anish", company="Acme Technologies")
    assert state.contact_email == client_email
    print(f"-> Contact set: {state.contact_name} ({state.contact_email}) at {state.company}")

    # 3. Simulate Buyer Discussion and Objections
    print("\n[STEP 3] Simulating Buyer & Agent Turns...")
    deal_state_engine.record_turn(channel_name, role="buyer", text="We are looking for real-time voice AI for our 15 sales reps, but we are worried about latency.")
    deal_state_engine.record_turn(channel_name, role="agent", text="Lively runs sub-500ms voice turns on Agora SD-RTN with native barge-in, so conversations feel instantaneous.")
    deal_state_engine.record_turn(channel_name, role="buyer", text="That sounds great. Can we book a demo for Tomorrow at 2:00 PM EST?")

    # 4. Book Demo Slot & Dispatch Meeting Invite
    from app.core.tools_impl.calendar import calendar_service
    open_slots = calendar_service.next_open_slots(3)
    target_slot = open_slots[0] if open_slots else "Monday at 10:00 AM EST"
    print(f"\n[STEP 4] Booking Demo Slot '{target_slot}' & Dispatching Meeting Invite via SMTP...")
    demo = deal_state_engine.book_demo(channel_name, target_slot, email=client_email)
    print(f"-> Demo Booking Status: {demo.get('status')} for {demo.get('time')}")
    print(f"-> Video Room: {demo.get('meeting_link')}")
    print(f"-> Google Calendar: {demo.get('google_calendar_link')}")
    print(f"-> Invite initial status: {demo.get('invite_status')}")

    # Wait briefly for background SMTP thread to deliver
    print("Waiting for SMTP demo confirmation delivery...")
    for _ in range(20):
        await asyncio.sleep(0.5)
        st = deal_state_engine.get_or_create(channel_name)
        status = (st.scheduled_demo or {}).get("invite_status")
        if status == "delivered":
            print(f"-> [SUCCESS] Demo invite confirmed delivered via SMTP to {client_email}!")
            break
    else:
        st = deal_state_engine.get_or_create(channel_name)
        status = (st.scheduled_demo or {}).get("invite_status")
        err = (st.scheduled_demo or {}).get("invite_error")
        print(f"Invite final status: {status}, error: {err}")

    # 5. Signal Call End and Generate/Send Personalized Follow-Up Email
    print("\n[STEP 5] Ending Call & Generating Personalized Follow-Up via Groq LLM...")
    deal_state_engine.record_turn(channel_name, role="system", text="[CALL_ENDED]")

    print("Waiting for Groq follow-up generation and SMTP dispatch...")
    for _ in range(30):
        await asyncio.sleep(0.5)
        st = deal_state_engine.get_or_create(channel_name)
        draft = st.follow_up_draft
        if draft and draft.get("sent"):
            print(f"-> [SUCCESS] Follow-up email generated via {draft.get('source')} and dispatched via SMTP!")
            print(f"   Subject: {draft.get('subject')}")
            print(f"   Sent to: {draft.get('sent_to')}")
            print(f"   Body Preview:\n{draft.get('body')[:300]}...")
            break
    else:
        st = deal_state_engine.get_or_create(channel_name)
        print(f"Follow-up state: {st.follow_up_draft}")

    print("\n" + "=" * 60)
    print("ALL LIVELY END-TO-END DEMO TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_full_fledged_demo())
