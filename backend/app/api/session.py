from typing import Optional
from fastapi import APIRouter, Request
from pydantic import BaseModel
from app.config import settings
from app.core.deal_state_engine import deal_state_engine
from app.core.security import client_ip, enforce_rate_limit, issue_session_token, new_channel_name, parse_session_token

router = APIRouter(prefix="/api", tags=["session"])


class SessionRequest(BaseModel):
    resume_token: Optional[str] = None


@router.post("/session")
async def create_session(request: Request, req: Optional[SessionRequest] = None):
    """
    Gives each visitor their own private channel and a signed token for it. Sending a still-valid
    token back resumes the same conversation (for example after a page refresh).
    """
    channel = parse_session_token(req.resume_token if req else None)
    resumed = bool(channel)
    if not channel:
        enforce_rate_limit(f"session:{client_ip(request)}", settings.RATE_LIMIT_SESSIONS_PER_HOUR, 3600,
                           "Too many new sessions from this address. Try again later.")
        channel = new_channel_name()
    token, expires_at = issue_session_token(channel)
    deal_state_engine.get_or_create(channel)
    return {"status": "success", "channel_name": channel, "session_token": token, "expires_at": expires_at, "resumed": resumed}
