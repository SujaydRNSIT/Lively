import json
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Header, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from app.config import settings
from app.services.agora_convo_api import agora_convo_service
from app.services.agora_token import build_rtc_token
from app.db.redis_client import redis_client

logger = logging.getLogger("lively.api.agora_agent")
router = APIRouter(prefix="/api/agent", tags=["agent_session"])

class AgentStartRequest(BaseModel):
    channel_name: str
    customer_uid: int | str = 1001

class AgentStopRequest(BaseModel):
    agent_id: Optional[str] = None
    channel_name: Optional[str] = None

class AgentStartResponse(BaseModel):
    status: str
    agent_id: str
    channel_name: str
    agent_rtc_uid: int
    customer_uid: int | str
    customer_token: str
    app_id: str
    mock: Optional[bool] = False

# Task 3.4: Auth dependency protecting /api/agent/*
async def verify_lively_auth(
    x_lively_key: Optional[str] = Header(default=None, alias="X-Lively-Key"),
    authorization: Optional[str] = Header(default=None)
):
    """
    Task 3.4: Protect /api/agent/* with a simple API key/session check.
    Frontend never holds Agora REST credentials.
    """
    if settings.DEBUG:
        return True

    expected_key = settings.LIVELY_API_KEY
    if x_lively_key and x_lively_key == expected_key:
        return True

    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        if token == expected_key:
            return True

    raise HTTPException(status_code=401, detail="Unauthorized: Invalid Lively session key")

@router.post("/start", response_model=AgentStartResponse, dependencies=[Depends(verify_lively_auth)])
async def start_agent_session(req: AgentStartRequest):
    """
    Task 3.2: Start agent session
    1. Generates customer RTC token and agent RTC token.
    2. Calls Agora Conversational AI REST API with our custom LLM endpoint.
    3. Persists agent_id to Redis/memory session store.
    4. Returns agent_id, channel_name, customer_token, customer_uid to frontend.
    """
    customer_uid = req.customer_uid
    agent_rtc_uid = settings.AGORA_AGENT_RTC_UID

    # 1. Generate Customer RTC token for frontend to join
    customer_token = build_rtc_token(
        app_id=settings.AGORA_APP_ID,
        app_cert=settings.AGORA_APP_CERTIFICATE,
        channel_name=req.channel_name,
        uid=customer_uid
    )

    # 2. Start Conversational AI agent in Agora
    agora_res = await agora_convo_service.start_agent(
        channel_name=req.channel_name,
        customer_uid=customer_uid,
        agent_rtc_uid=agent_rtc_uid
    )

    agent_id = agora_res.get("agent_id", f"agent_sess_{req.channel_name}")

    # 3. Store agent_id against the session in Redis
    session_data = {
        "agent_id": agent_id,
        "channel_name": req.channel_name,
        "customer_uid": customer_uid,
        "agent_rtc_uid": agent_rtc_uid,
        "status": "RUNNING"
    }
    await redis_client.set(f"session:{req.channel_name}", json.dumps(session_data), expire=7200)
    await redis_client.set(f"agent:{agent_id}", json.dumps(session_data), expire=7200)

    # 4. Return to frontend
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

@router.post("/stop", dependencies=[Depends(verify_lively_auth)])
async def stop_agent_session(req: AgentStopRequest):
    """
    Task 3.3: Stop agent session.
    Accepts agent_id or resolves it via channel_name from Redis.
    """
    agent_id = req.agent_id
    if not agent_id and req.channel_name:
        stored = await redis_client.get(f"session:{req.channel_name}")
        if stored:
            try:
                data = json.loads(stored)
                agent_id = data.get("agent_id")
            except Exception:
                pass

    if not agent_id:
        agent_id = f"agent_sess_{req.channel_name or 'unknown'}"

    res = await agora_convo_service.stop_agent(agent_id)
    
    if req.channel_name:
        await redis_client.delete(f"session:{req.channel_name}")
    await redis_client.delete(f"agent:{agent_id}")

    return {"status": "success", "result": res}

@router.get("/status/{agent_id}", dependencies=[Depends(verify_lively_auth)])
async def query_agent_status(agent_id: str):
    """
    Task 3.3: Query agent status and metrics from Agora REST API.
    """
    res = await agora_convo_service.query_agent(agent_id)
    return {"status": "success", "result": res}
