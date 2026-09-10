"""
SmartDialer REST API (Feature C).

Endpoints:
  POST   /api/dialer/campaigns          — create a campaign with a lead list
  GET    /api/dialer/campaigns           — list all campaigns
  GET    /api/dialer/campaigns/{id}      — get campaign snapshot
  POST   /api/dialer/campaigns/{id}/start  — start dialing
  POST   /api/dialer/campaigns/{id}/pause  — pause dialing
  POST   /api/dialer/campaigns/{id}/reset-breaker — reset safety circuit breaker
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.dialer.campaign import campaign_runner

logger = logging.getLogger("lively.api.dialer")
router = APIRouter(prefix="/api/dialer", tags=["dialer"])


# --------------------------------------------------------------------------- #
# Request models                                                                #
# --------------------------------------------------------------------------- #

class LeadInput(BaseModel):
    name:    str = "Lead"
    phone:   str = ""
    company: str = ""


class CreateCampaignRequest(BaseModel):
    name:      str              = "Outbound Campaign"
    leads:     List[LeadInput]  = Field(default_factory=list)
    ai_slots:  int              = 3     # AI agent slots allocated to this campaign


# --------------------------------------------------------------------------- #
# Routes                                                                        #
# --------------------------------------------------------------------------- #

@router.post("/campaigns", status_code=201)
async def create_campaign(req: CreateCampaignRequest) -> Dict[str, Any]:
    """Create a new outbound campaign with a lead list."""
    if not req.leads:
        raise HTTPException(status_code=400, detail="At least one lead is required.")
    if len(req.leads) > 200:
        raise HTTPException(status_code=400, detail="Maximum 200 leads per campaign (demo limit).")

    leads_data = [l.model_dump() for l in req.leads]
    campaign_id = campaign_runner.create_campaign(
        name       = req.name,
        leads_data = leads_data,
        ai_slots   = max(1, min(req.ai_slots, 10)),
    )
    snap = campaign_runner.snapshot(campaign_id)
    return {"status": "created", "campaign_id": campaign_id, "data": snap.to_dict() if snap else {}}


@router.get("/campaigns")
async def list_campaigns() -> Dict[str, Any]:
    """List all campaigns with their current snapshots."""
    return {"status": "ok", "campaigns": campaign_runner.list_campaigns()}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str) -> Dict[str, Any]:
    """Get the live snapshot for one campaign."""
    snap = campaign_runner.snapshot(campaign_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return {"status": "ok", "data": snap.to_dict()}


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str) -> Dict[str, Any]:
    """Start or resume dialing."""
    try:
        campaign_runner.start(campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    snap = campaign_runner.snapshot(campaign_id)
    return {"status": "started", "data": snap.to_dict() if snap else {}}


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str) -> Dict[str, Any]:
    """Pause all dialing for this campaign."""
    campaign_runner.pause(campaign_id)
    snap = campaign_runner.snapshot(campaign_id)
    return {"status": "paused", "data": snap.to_dict() if snap else {}}


@router.post("/campaigns/{campaign_id}/reset-breaker")
async def reset_circuit_breaker(campaign_id: str) -> Dict[str, Any]:
    """Manually reset the safety circuit breaker for this campaign."""
    safety = campaign_runner._safety.get(campaign_id)
    if not safety:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    safety.reset_circuit_breaker()
    snap = campaign_runner.snapshot(campaign_id)
    return {"status": "breaker_reset", "data": snap.to_dict() if snap else {}}
