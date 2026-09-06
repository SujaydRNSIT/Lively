import logging
import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.core.tools_impl.calendar import book_calendar_slot
from app.core.tools_impl.crm import sync_crm_deal, log_activity
from app.core.tools_impl.escalation import trigger_human_escalation
from app.core.deal_state_engine import deal_state_engine
from app.core.email_service import send_meeting_invite_email
from app.models.schemas import DealStageEnum
from app.routers.telemetry import ws_manager
from app.services.email_service import email_service

logger = logging.getLogger("lively.api.tools")
router = APIRouter(prefix="/api/tools", tags=["tools"])

class CalendarBookingRequest(BaseModel):
    channel_name: str
    time_slot: str
    email: Optional[str] = "prospect@example.com"
    topic: Optional[str] = "Lively Voice AI Architecture Demo"

class CRMSyncRequest(BaseModel):
    channel_name: str
    company: str
    stage: str
    deal_value: str
    notes: Optional[str] = ""

class EscalationRequest(BaseModel):
    channel_name: str
    reason: str
    urgency: Optional[str] = "medium"

class MeetingInviteRequest(BaseModel):
    channel_name: str
    email: str
    meeting_time: Optional[str] = "Tomorrow at 2:00 PM EST"
    meeting_link: Optional[str] = "https://meet.google.com/new"
    topic: Optional[str] = "Lively Real-Time Voice AI Sales Deep-Dive"

@router.post("/book-demo")
async def api_book_demo(req: CalendarBookingRequest):
    state = deal_state_engine.get_or_create(req.channel_name)
    email = req.email
    if not email or email == "prospect@example.com":
        if state.contact_email and "@" in state.contact_email:
            email = state.contact_email
        elif state.crm_lead and getattr(state.crm_lead, "contact_email", None):
            email = state.crm_lead.contact_email
        else:
            email = "alex.rivera@nextgen.ai"

    meeting_id = f"mtg_{int(time.time()*1000)}"
    meeting_link = "https://meet.google.com/new"
    topic = req.topic or "Lively Real-Time Voice AI Sales Deep-Dive"

    prep = email_service.prepare_demo_confirmation(email, {
        "time": req.time_slot,
        "topic": topic,
        "meeting_link": meeting_link,
        "meeting_id": meeting_id
    })

    demo_record = {
        "meeting_id": meeting_id,
        "status": "CONFIRMED",
        "time": req.time_slot,
        "email": email,
        "topic": topic,
        "host": "Senior Solutions Architect",
        "meeting_link": meeting_link,
        "google_calendar_link": prep["google_calendar_url"],
        "booked_at": time.time(),
        "message": f"Demo locked & confirmed for {req.time_slot}. Calendar invite dispatched to {email}."
    }

    state.scheduled_demo = demo_record
    state.stage = DealStageEnum.DEMO_SCHEDULING
    state.crm_lead.status = "Demo_Scheduled"
    
    booking_note = f"Demo booked: {req.time_slot} ({email})"
    if booking_note not in state.action_items:
        state.action_items.append(booking_note)

    email_note = f"Invite dispatched: {email} (Google Meet + Calendar blocked)"
    if email_note not in state.action_items:
        state.action_items.append(email_note)

    # Dispatch email
    try:
        email_service.send_demo_confirmation(email, demo_record)
    except Exception as e:
        logger.error(f"Failed to dispatch demo confirmation email: {e}")

    await ws_manager.broadcast_state(req.channel_name, {
        "type": "DEAL_STATE_UPDATE",
        "data": state.model_dump()
    })
    return {"status": "success", "data": demo_record}

@router.post("/sync-crm")
async def api_sync_crm(req: CRMSyncRequest):
    res = await sync_crm_deal(req.company, req.stage, req.deal_value, req.notes)
    state = deal_state_engine.get_or_create(req.channel_name)
    state.crm_lead.company = req.company
    state.crm_lead.status = req.stage
    state.crm_lead.deal_value = req.deal_value
    stage_value = DealStageEnum(req.stage) if req.stage in {e.value for e in DealStageEnum} else req.stage
    state.stage = stage_value
    await ws_manager.broadcast_state(req.channel_name, {
        "type": "DEAL_STATE_UPDATE",
        "data": state.model_dump()
    })
    return {"status": "success", "data": res}

@router.post("/escalate")
async def api_escalate(req: EscalationRequest):
    res = await trigger_human_escalation(req.reason, req.urgency)
    state = deal_state_engine.get_or_create(req.channel_name)
    state.stage = DealStageEnum.ESCALATED
    state.action_items.append(f"Escalated: {req.reason}")
    await ws_manager.broadcast_state(req.channel_name, {
        "type": "DEAL_STATE_UPDATE",
        "data": state.model_dump()
    })
    return {"status": "success", "data": res}

@router.post("/send-meeting-invite")
async def api_send_meeting_invite(req: MeetingInviteRequest):
    """
    Dispatches Google Meet invitation to prospect's email, generates Google Calendar link, and binds to Deal State.
    """
    clean_email = req.email.strip()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    state = deal_state_engine.get_or_create(req.channel_name)
    state.contact_email = clean_email
    
    # Update scheduled demo record
    meeting_link = req.meeting_link or "https://meet.google.com/new"
    time_slot = req.meeting_time or (state.scheduled_demo.get("time") if state.scheduled_demo else "Tomorrow at 2:00 PM EST")
    topic = req.topic or "Lively Real-Time Voice AI Sales Deep-Dive"
    meeting_id = f"mtg_{int(time.time()*1000)}"

    prep = email_service.prepare_demo_confirmation(clean_email, {
        "time": time_slot,
        "topic": topic,
        "meeting_link": meeting_link,
        "meeting_id": meeting_id
    })
    
    demo_record = {
        "meeting_id": meeting_id,
        "status": "CONFIRMED",
        "time": time_slot,
        "email": clean_email,
        "topic": topic,
        "host": "Senior Solutions Architect",
        "meeting_link": meeting_link,
        "google_calendar_link": prep["google_calendar_url"],
        "invite_sent": True,
        "sent_at": time.time(),
        "message": f"Google Meet invitation & calendar block dispatched to {clean_email} for {time_slot}."
    }
    state.scheduled_demo = demo_record
    state.stage = DealStageEnum.DEMO_SCHEDULING
    
    # Physically dispatch via SMTP if configured
    email_res = await send_meeting_invite_email(
        to_email=clean_email,
        topic=demo_record["topic"],
        time_slot=time_slot,
        meeting_link=meeting_link,
        host=demo_record["host"]
    )
    delivered = email_res.get("delivered", False)
    demo_record["delivered"] = delivered
    demo_record["delivery_detail"] = email_res

    # Log in CRM activity
    await log_activity(
        company_name=state.company or "Prospect Company",
        activity_type="Meeting Invite Dispatched",
        summary=f"Google Meet link ({meeting_link}) invite processed for {clean_email} (delivered={delivered})."
    )
    
    invite_note = f"Invite processed: {clean_email} ({time_slot})"
    if invite_note not in state.action_items:
        state.action_items.append(invite_note)
        
    # Dispatch email with full calendar attachments and previews
    dispatch_res = email_service.send_demo_confirmation(clean_email, demo_record)
    effective_delivered = delivered or dispatch_res.get("delivered", False)
    demo_record["delivered"] = effective_delivered

    logger.info(f"Meeting invite processed for {clean_email} on channel {req.channel_name} (delivered={effective_delivered}, mode={dispatch_res.get('mode')})")

    # Broadcast updated deal state to frontend
    await ws_manager.broadcast_state(req.channel_name, {
        "type": "DEAL_STATE_UPDATE",
        "data": state.model_dump()
    })

    if effective_delivered:
        resp_message = f"Google Meet invite successfully delivered to {clean_email}!"
    else:
        resp_message = (
            f"Demo scheduled for {time_slot}! "
            f"(Note: To receive physical emails in your inbox, set SMTP_USER and SMTP_PASSWORD in .env, "
            f"or click 'Open in Gmail' to send with 1 click)."
        )

    return {
        "status": "success",
        "delivered": effective_delivered,
        "message": resp_message,
        "data": demo_record,
        "dispatch": dispatch_res
    }

