from typing import Optional
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.deal_state_engine import deal_state_engine
from app.core.security import channel_path_access
from app.core.understanding import extract_email
from app.routers.telemetry import ws_manager

logger = logging.getLogger("lively.api.deal_state")
# Every route here is scoped to the caller's own channel via their session token.
router = APIRouter(prefix="/api/deal-state", tags=["deal_state"], dependencies=[Depends(channel_path_access)])

class ResolveObjectionRequest(BaseModel):
    objection_id: str

class SetContactRequest(BaseModel):
    email: str
    name: Optional[str] = None
    company: Optional[str] = None

@router.get("/{channel_name}")
async def get_deal_state(channel_name: str):
    """
    Returns current Deal State snapshot for the specified channel.
    """
    state = deal_state_engine.get_or_create(channel_name)
    return {"status": "success", "data": state.model_dump()}

@router.post("/{channel_name}/set-contact")
async def set_deal_contact(channel_name: str, req: SetContactRequest):
    """
    Sets the prospect's contact details. If a demo is already booked, the invite goes to this address.
    """
    clean_email = req.email.strip()
    if extract_email(clean_email) != clean_email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    state = deal_state_engine.set_contact(channel_name, clean_email, req.name, req.company)
    logger.info(f"Updated contact on channel {channel_name}: {clean_email} ({state.contact_name})")
    await ws_manager.broadcast_state(channel_name, {"type": "DEAL_STATE_UPDATE", "data": state.model_dump()})
    return {"status": "success", "data": state.model_dump()}

@router.post("/{channel_name}/resolve-objection")
async def resolve_deal_objection(channel_name: str, req: ResolveObjectionRequest):
    """
    Marks an active objection as resolved and triggers WebSocket telemetry broadcast.
    """
    updated = deal_state_engine.resolve_objection(channel_name, req.objection_id)
    await ws_manager.broadcast_state(channel_name, {"type": "DEAL_STATE_UPDATE", "data": updated.model_dump()})
    return {"status": "success", "data": updated.model_dump()}

@router.post("/{channel_name}/reset")
async def reset_channel_deal_state(channel_name: str):
    """
    Resets the Deal State for the specified channel to a clean initial state.
    """
    new_state = deal_state_engine.reset_state(channel_name)
    await ws_manager.broadcast_state(channel_name, {"type": "DEAL_STATE_UPDATE", "data": new_state.model_dump()})
    return {"status": "success", "data": new_state.model_dump()}

@router.post("/{channel_name}/call-end")
async def mark_call_ended(channel_name: str):
    """
    Signals that the voice call has ended.
    Triggers background follow-up email draft generation (Feature D).
    """
    # Sending the special sentinel text triggers _generate_follow_up in the engine
    deal_state_engine.record_turn(channel_name, role="system", text="[CALL_ENDED]")
    state = deal_state_engine.get_or_create(channel_name)
    return {"status": "success", "message": "Follow-up draft generation started", "data": state.model_dump()}
