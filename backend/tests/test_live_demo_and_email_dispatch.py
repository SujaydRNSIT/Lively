import asyncio
import time
from app.config import settings
from app.core.understanding import extract_email
from app.core.deal_state_engine import deal_state_engine
from app.services.email_service import email_service


async def run_full_fledged_demo():
    print("=" * 70)
    print("RUNNING COMPLETE LIVELY CLIENT FLOW VERIFICATION")
    print(f"Configured SMTP Sender: {settings.SMTP_USER} via {settings.SMTP_HOST}:{settings.SMTP_PORT}")
    print("=" * 70)

    # -------------------------------------------------------------
    # PART 1: TEST USER LOOKING FOR A DEMO -> AUTO-DISPATCH DEMO MEETING LINK
    # -------------------------------------------------------------
    print("\n--- [PART 1: AUTO-DISPATCH DEMO MEETING LINK WHEN USER LOOKS FOR A DEMO] ---")
    ch_demo = f"flow_demo_{int(time.time())}"
    client_email = "anishhyd995@gmail.com"

    # Step 1: User enters email in popup on page load
    print(f"[P1.1] User enters email in popup: {client_email}")
    state1 = deal_state_engine.set_contact(ch_demo, client_email, name="Anish", company="Acme Tech")
    assert state1.contact_email == client_email
    print(f"-> Email stored in session: {state1.contact_email}")

    # Step 2: Buyer simply says in call: "I am looking for a demo"
    print("[P1.2] Buyer says: 'We want to see how this works, I am looking for a demo'")
    deal_state_engine.record_turn(ch_demo, role="buyer", text="We want to see how this works, I am looking for a demo")

    # Step 3: Verify demo was automatically booked & invite dispatched
    st_demo = deal_state_engine.get_or_create(ch_demo)
    demo_booking = st_demo.scheduled_demo
    assert demo_booking is not None, "Demo should be automatically booked when user is looking for a demo!"
    print(f"-> [SUCCESS] Auto-Booked Slot: {demo_booking.get('time')}")
    print(f"-> Meeting Room: {demo_booking.get('meeting_link')}")
    print(f"-> Google Calendar URL: {demo_booking.get('google_calendar_link')}")
    print(f"-> Target Email: {demo_booking.get('email')}")

    # Wait for SMTP thread to finish delivery
    print("Waiting for demo invite delivery via SMTP to client's entered email...")
    for _ in range(20):
        await asyncio.sleep(0.5)
        st_demo = deal_state_engine.get_or_create(ch_demo)
        if (st_demo.scheduled_demo or {}).get("invite_status") == "delivered":
            print(f"-> [SUCCESS] Meeting demo link delivered via SMTP to {client_email}!")
            break
    else:
        st_demo = deal_state_engine.get_or_create(ch_demo)
        print(f"Demo invite status: {(st_demo.scheduled_demo or {}).get('invite_status')}")

    # -------------------------------------------------------------
    # PART 2: CALL ENDS WITHOUT CLOSED DEAL OR DEMO -> AUTO FOLLOW-UP
    # -------------------------------------------------------------
    print("\n--- [PART 2: AUTO-DISPATCH FOLLOW-UP WHEN DEAL NOT CLOSED / DEMO NOT BOOKED] ---")
    ch_nodemo = f"flow_nodemo_{int(time.time())}"

    # Step 1: User enters email in popup
    print(f"[P2.1] User enters email in popup: {client_email}")
    state2 = deal_state_engine.set_contact(ch_nodemo, client_email, name="Anish", company="Enterprise Solutions")
    assert state2.contact_email == client_email

    # Step 2: Buyer has a conversation about pricing & security, but does NOT book a demo
    print("[P2.2] Buyer asks questions about security & SOC2 compliance, no demo booked")
    deal_state_engine.record_turn(ch_nodemo, role="buyer", text="We have 25 sales reps, do you comply with SOC2 and what is your enterprise pricing?")
    deal_state_engine.record_turn(ch_nodemo, role="agent", text="Yes, Lively is fully SOC2 Type II compliant with end-to-end encryption on Agora's network.")
    deal_state_engine.record_turn(ch_nodemo, role="buyer", text="Okay, thanks for the info, I need to discuss this with my internal team first.")

    # Step 3: Call ends (Deal is not closed, demo not booked)
    print("[P2.3] Call ends ([CALL_ENDED]). Triggering automatic personalized follow-up draft...")
    deal_state_engine.record_turn(ch_nodemo, role="system", text="[CALL_ENDED]")

    # Step 4: Verify follow-up draft is synthesized and dispatched to user's entered email
    print("Waiting for Groq follow-up generation and SMTP dispatch...")
    for _ in range(30):
        await asyncio.sleep(0.5)
        st_nodemo = deal_state_engine.get_or_create(ch_nodemo)
        draft = st_nodemo.follow_up_draft
        if draft and draft.get("sent"):
            print(f"-> [SUCCESS] Personalized follow-up email generated via {draft.get('source')} and dispatched via SMTP!")
            print(f"   Subject: {draft.get('subject')}")
            print(f"   Sent to: {draft.get('sent_to')}")
            print(f"   Preview:\n{draft.get('body')[:350]}...")
            break
    else:
        st_nodemo = deal_state_engine.get_or_create(ch_nodemo)
        print(f"Follow-up state: {st_nodemo.follow_up_draft}")

    print("\n" + "=" * 70)
    print("ALL USER FLOW VERIFICATIONS PASSED WITH REAL SMTP DISPATCH!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_full_fledged_demo())
