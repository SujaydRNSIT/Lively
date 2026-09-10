import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.core.deal_state_engine import deal_state_engine
from app.core.security import require_channel_access, enforce_rate_limit, client_ip
from app.core.tools_impl.crm import sync_crm_deal, crm_service
from app.core.understanding import extract_email
from app.models.schemas import DealStageEnum
from app.routers.telemetry import ws_manager

logger = logging.getLogger("lively.api.tools")
router = APIRouter(prefix="/api/tools", tags=["tools"])

class CalendarBookingRequest(BaseModel):
    channel_name: str
    time_slot: str
    email: Optional[str] = None
    topic: Optional[str] = None

class CRMSyncRequest(BaseModel):
    channel_name: str
    company: str
    stage: str
    deal_value: Optional[str] = None
    notes: Optional[str] = ""

class EscalationRequest(BaseModel):
    channel_name: str
    reason: str = "Buyer asked for a human account executive."
    urgency: Optional[str] = "High"

class MeetingInviteRequest(BaseModel):
    channel_name: str
    email: str

async def _broadcast(channel_name: str) -> None:
    state = deal_state_engine.get_or_create(channel_name)
    await ws_manager.broadcast_state(channel_name, {"type": "DEAL_STATE_UPDATE", "data": state.model_dump()})

@router.post("/book-demo")
async def api_book_demo(req: CalendarBookingRequest, x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")):
    """Books a demo with the same availability rules the voice agent uses."""
    require_channel_access(req.channel_name, x_lively_session)
    result = deal_state_engine.book_demo(req.channel_name, req.time_slot, req.email, req.topic)
    await _broadcast(req.channel_name)
    if result.get("status") == "UNAVAILABLE":
        return JSONResponse(status_code=409, content={"status": "unavailable", "data": result})
    return {"status": "success", "data": result}

@router.post("/sync-crm")
async def api_sync_crm(req: CRMSyncRequest, x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")):
    require_channel_access(req.channel_name, x_lively_session)
    res = await sync_crm_deal(req.company, req.stage, req.deal_value, req.notes or "")
    state = deal_state_engine.get_or_create(req.channel_name)
    state.company = req.company
    state.crm_lead.company = req.company
    if req.deal_value:
        state.crm_lead.deal_value = req.deal_value
    if req.stage in {e.value for e in DealStageEnum}:
        state.stage = DealStageEnum(req.stage)
    crm_service.record_activity(state, "crm_update", f"CRM updated manually: {req.company} -> {req.stage}")
    crm_service.upsert_from_state(state)
    await _broadcast(req.channel_name)
    return {"status": "success", "data": res}

@router.post("/escalate")
async def api_escalate(req: EscalationRequest, x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")):
    """Hands this channel's conversation (qualification, objections, transcript) to a human AE."""
    require_channel_access(req.channel_name, x_lively_session)
    record = deal_state_engine.escalate(req.channel_name, req.reason, req.urgency or "High", trigger="manual")
    await _broadcast(req.channel_name)
    return {"status": "success", "data": {"status": "HOT_TRANSFER_INITIATED", **record}}

@router.post("/send-meeting-invite")
async def api_send_meeting_invite(
    req: MeetingInviteRequest,
    request: Request,
    x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")
):
    """
    Sends (or re-sends) the invite for this channel's confirmed demo to the given address.
    The meeting link and time come from the booking, never from the request.
    """
    require_channel_access(req.channel_name, x_lively_session)
    clean_email = req.email.strip()
    if extract_email(clean_email) != clean_email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    enforce_rate_limit(f"invite-ip:{client_ip(request)}", 10, 3600, "Too many invite requests. Try again later.")

    demo = deal_state_engine.send_invite(req.channel_name, clean_email)
    if not demo:
        raise HTTPException(status_code=400, detail="No confirmed demo yet. Book a time first.")
    await _broadcast(req.channel_name)

    if demo.get("invite_status") == "rate_limited":
        message = "Invite limit reached for this conversation. Try again later."
    else:
        message = f"Invite for {demo['time']} is on its way to {clean_email}."
    logger.info(f"Meeting invite requested for {clean_email} on channel {req.channel_name} ({demo.get('invite_status')})")
    return {"status": "success", "message": message, "data": demo}
