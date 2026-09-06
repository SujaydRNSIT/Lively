from typing import Optional
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.deal_state_engine import deal_state_engine
from app.routers.telemetry import ws_manager

logger = logging.getLogger("lively.api.deal_state")
router = APIRouter(prefix="/api/deal-state", tags=["deal_state"])

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
    Sets the prospect's contact information (email, name, company) upon entering the system.
    Propagates to DealState and CRM lead, updates scheduled demo email, and broadcasts to WebSocket telemetry.
    """
    clean_email = req.email.strip()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    state = deal_state_engine.get_or_create(channel_name)
    state.contact_email = clean_email
    state.crm_lead.contact_email = clean_email

    if req.name and req.name.strip():
        state.contact_name = req.name.strip()
        state.crm_lead.contact_name = req.name.strip()

    if req.company and req.company.strip():
        state.company = req.company.strip()
        state.crm_lead.company = req.company.strip()

    # If demo already exists with placeholder email, update it and dispatch invite
    if state.scheduled_demo:
        old_email = state.scheduled_demo.get("email", "")
        state.scheduled_demo["email"] = clean_email
        if "@nextgen.ai" in old_email or not old_email or old_email != clean_email:
            try:
                from app.services.email_service import email_service
                email_service.send_demo_confirmation(clean_email, state.scheduled_demo)
                logger.info(f"Dispatched demo invitation to newly registered contact email: {clean_email}")
            except Exception as e_dispatch:
                logger.warning(f"Could not dispatch email on set-contact: {e_dispatch}")

    logger.info(f"Updated contact on channel {channel_name}: {clean_email} ({state.contact_name})")

    await ws_manager.broadcast_state(channel_name, {
        "type": "DEAL_STATE_UPDATE",
        "data": state.model_dump()
    })

    return {"status": "success", "data": state.model_dump()}

@router.post("/{channel_name}/resolve-objection")
async def resolve_deal_objection(channel_name: str, req: ResolveObjectionRequest):
    """
    Marks an active objection as resolved and triggers WebSocket telemetry broadcast.
    """
    updated = deal_state_engine.resolve_objection(channel_name, req.objection_id)
    if updated:
        await ws_manager.broadcast_state(channel_name, {
            "type": "DEAL_STATE_UPDATE",
            "data": updated.model_dump()
        })
    return {"status": "success", "data": updated.model_dump() if updated else {}}
 
@router.post("/{channel_name}/reset")
async def reset_channel_deal_state(channel_name: str):
    """
    Resets the Deal State for the specified channel to a clean initial state.
    """
    new_state = deal_state_engine.reset_state(channel_name)
    await ws_manager.broadcast_state(channel_name, {
        "type": "DEAL_STATE_UPDATE",
        "data": new_state.model_dump()
    })
    return {"status": "success", "data": new_state.model_dump()}
