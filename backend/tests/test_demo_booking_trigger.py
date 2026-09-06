import pytest
from app.models.schemas import DealState, DealStageEnum, ChatTurn
from app.core.deal_state_engine import deal_state_engine

def test_no_false_positives_for_greetings_and_inquiries():
    channel = "test_fp_channel_1"
    
    # 1. Greetings should never book a demo
    state = deal_state_engine.record_turn(channel, "buyer", "Good morning!")
    assert state.scheduled_demo is None

    state = deal_state_engine.record_turn(channel, "buyer", "Good afternoon, how are you?")
    assert state.scheduled_demo is None

    # 2. Questions with "call" should never book a demo
    state = deal_state_engine.record_turn(channel, "buyer", "What is the latency on this call?")
    assert state.scheduled_demo is None

    state = deal_state_engine.record_turn(channel, "buyer", "Can you hear me on this call?")
    assert state.scheduled_demo is None

    # 3. Voice demo inquiry should never book a calendar demo
    state = deal_state_engine.record_turn(channel, "buyer", "Can you give me a demo of your voice?")
    assert state.scheduled_demo is None

    state = deal_state_engine.record_turn(channel, "buyer", "Show me a demo")
    assert state.scheduled_demo is None

    # 4. General agreements to non-scheduling questions
    deal_state_engine.record_turn(channel, "agent", "Are you currently using Twilio for telephony?")
    state = deal_state_engine.record_turn(channel, "buyer", "Yes, exactly.")
    assert state.scheduled_demo is None


def test_agent_cannot_hallucinate_booking_without_buyer_consent():
    channel = "test_fp_agent_hallucination"

    deal_state_engine.record_turn(channel, "buyer", "What are your pricing plans?")
    # Agent claims it booked a slot even though buyer only asked about pricing
    state = deal_state_engine.record_turn(
        channel,
        "agent",
        "Starter is one ninety-nine dollars. I have booked a demo walkthrough for you tomorrow at two PM EST."
    )
    # Protection must prevent false booking
    assert state.scheduled_demo is None


def test_explicit_buyer_demo_booking():
    channel = "test_tp_explicit_booking"

    state = deal_state_engine.record_turn(
        channel,
        "buyer",
        "Can we schedule a demo for tomorrow at 3 PM?"
    )
    assert state.scheduled_demo is not None
    assert state.scheduled_demo["status"] == "CONFIRMED"
    assert "Tomorrow" in state.scheduled_demo["time"]
    assert "3:00 PM" in state.scheduled_demo["time"]
    assert state.stage == DealStageEnum.DEMO_SCHEDULING


def test_buyer_accepts_agent_proposed_slot():
    channel = "test_tp_agent_proposal_accepted"

    deal_state_engine.record_turn(
        channel,
        "agent",
        "Would tomorrow at 2:00 PM EST work for our thirty-minute technical walkthrough?"
    )
    state = deal_state_engine.record_turn(
        channel,
        "buyer",
        "That works for me, lock it in!"
    )
    assert state.scheduled_demo is not None
    assert state.scheduled_demo["status"] == "CONFIRMED"
    assert "Tomorrow" in state.scheduled_demo["time"]
    assert "2:00 PM" in state.scheduled_demo["time"]


def test_rescheduling_existing_demo():
    channel = "test_reschedule_channel"

    # 1. Initial booking
    state = deal_state_engine.record_turn(
        channel,
        "buyer",
        "Please book a meeting for Monday at 10 AM"
    )
    assert state.scheduled_demo is not None
    assert "Monday" in state.scheduled_demo["time"]

    # 2. Intermediate turns shouldn't overwrite or duplicate booking
    state = deal_state_engine.record_turn(channel, "buyer", "Sounds great, thanks!")
    assert "Monday" in state.scheduled_demo["time"]

    # 3. Explicit reschedule request
    state = deal_state_engine.record_turn(
        channel,
        "buyer",
        "Can we reschedule to Friday at 4 PM instead?"
    )
    assert state.scheduled_demo is not None
    assert "Friday" in state.scheduled_demo["time"]
    assert "4:00 PM" in state.scheduled_demo["time"]
