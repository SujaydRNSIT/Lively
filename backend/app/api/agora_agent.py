import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.config import settings
from app.core.security import require_channel_access, parse_session_token
from app.services.agora_convo_api import agora_convo_service
from app.services.agora_token import build_rtc_token
from app.db.redis_client import redis_client
from app.core.deal_state_engine import deal_state_engine

logger = logging.getLogger("lively.api.agora_agent")
router = APIRouter(prefix="/api/agent", tags=["agent_session"])

class AgentStartRequest(BaseModel):
    channel_name: str
    customer_uid: int | str = 1001

class AgentStopRequest(BaseModel):
    agent_id: Optional[str] = None
    channel_name: str

class AgentStartResponse(BaseModel):
    status: str
    agent_id: str
    channel_name: str
    agent_rtc_uid: int
    customer_uid: int | str
    customer_token: str
    app_id: str
    mock: Optional[bool] = False

@router.post("/start", response_model=AgentStartResponse)
async def start_agent_session(
    req: AgentStartRequest,
    x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")
):
    """
    Task 3.2: Start agent session (only for the caller's own channel)
    1. Generates customer RTC token and agent RTC token.
    2. Calls Agora Conversational AI REST API with our custom LLM endpoint.
    3. Persists agent_id to Redis/memory session store.
    4. Returns agent_id, channel_name, customer_token, customer_uid to frontend.
    """
    require_channel_access(req.channel_name, x_lively_session)
    customer_uid = req.customer_uid
    agent_rtc_uid = settings.AGORA_AGENT_RTC_UID

    customer_token = build_rtc_token(
        app_id=settings.AGORA_APP_ID,
        app_cert=settings.AGORA_APP_CERTIFICATE,
        channel_name=req.channel_name,
        uid=customer_uid
    )

    agora_res = await agora_convo_service.start_agent(
        channel_name=req.channel_name,
        customer_uid=customer_uid,
        agent_rtc_uid=agent_rtc_uid
    )

    agent_id = agora_res.get("agent_id", f"agent_sess_{req.channel_name}")

    session_data = {
        "agent_id": agent_id,
        "channel_name": req.channel_name,
        "customer_uid": customer_uid,
        "agent_rtc_uid": agent_rtc_uid,
        "status": "RUNNING"
    }
    await redis_client.set(f"session:{req.channel_name}", json.dumps(session_data), expire=7200)
    await redis_client.set(f"agent:{agent_id}", json.dumps(session_data), expire=7200)

    return AgentStartResponse(
        status="success",
        agent_id=agent_id,
        channel_name=req.channel_name,
        agent_rtc_uid=agent_rtc_uid,
        customer_uid=customer_uid,
        customer_token=customer_token,
        app_id=settings.AGORA_APP_ID or "demo_app_id",
        mock=agora_res.get("mock", False)
    )

async def _agent_channel(agent_id: str) -> Optional[str]:
    stored = await redis_client.get(f"agent:{agent_id}")
    if not stored:
        return None
    try:
        return json.loads(stored).get("channel_name")
    except Exception:
        return None

@router.post("/stop")
async def stop_agent_session(
    req: AgentStopRequest,
    x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")
):
    """
    Task 3.3: Stop agent session. Accepts agent_id or resolves it via channel_name.
    """
    require_channel_access(req.channel_name, x_lively_session)
    agent_id = req.agent_id
    if agent_id:
        owner = await _agent_channel(agent_id)
        if owner and owner != req.channel_name:
            raise HTTPException(status_code=403, detail="That agent belongs to a different channel.")
    else:
        stored = await redis_client.get(f"session:{req.channel_name}")
        if stored:
            try:
                agent_id = json.loads(stored).get("agent_id")
            except Exception:
                pass

    if not agent_id:
        agent_id = f"agent_sess_{req.channel_name}"

    res = await agora_convo_service.stop_agent(agent_id)
    await redis_client.delete(f"session:{req.channel_name}")
    await redis_client.delete(f"agent:{agent_id}")
    deal_state_engine.record_turn(req.channel_name, role="system", text="[CALL_ENDED]")
    return {"status": "success", "result": res}

@router.get("/status/{agent_id}")
async def query_agent_status(
    agent_id: str,
    x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")
):
    """
    Task 3.3: Query agent status from Agora REST API (only agents started from the caller's channel).
    """
    channel = parse_session_token(x_lively_session)
    if not channel:
        raise HTTPException(status_code=401, detail="Missing or invalid session.")
    if await _agent_channel(agent_id) != channel:
        raise HTTPException(status_code=404, detail="Agent not found for this session.")
    res = await agora_convo_service.query_agent(agent_id)
    return {"status": "success", "result": res}
