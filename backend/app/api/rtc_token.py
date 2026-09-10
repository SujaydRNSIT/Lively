import logging
from typing import Optional
from fastapi import APIRouter, Header
from app.config import settings
from app.core.security import require_channel_access
from app.models.schemas import RtcTokenRequest, RtcTokenResponse
from app.services.agora_token import build_rtc_token

logger = logging.getLogger("lively.api.rtc_token")
router = APIRouter(prefix="/api", tags=["rtc_token"])

@router.post("/rtc-token", response_model=RtcTokenResponse)
@router.post("/agora/token", response_model=RtcTokenResponse)
async def generate_rtc_token(
    req: RtcTokenRequest,
    x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")
):
    """
    Task 3.1: Given channel_name and uid, generate a short-lived Agora RTC token.
    Only issued for the caller's own channel, so nobody can mint a token to join someone else's call.
    """
    require_channel_access(req.channel_name, x_lively_session)
    token = build_rtc_token(
        app_id=settings.AGORA_APP_ID,
        app_cert=settings.AGORA_APP_CERTIFICATE,
        channel_name=req.channel_name,
        uid=req.uid,
        role=req.role
    )
    return RtcTokenResponse(
        status="success",
        channel_name=req.channel_name,
        uid=req.uid,
        token=token,
        app_id=settings.AGORA_APP_ID or "demo_app_id"
    )

@router.get("/agora/config")
async def get_agora_config():
    return {
        "app_id": settings.AGORA_APP_ID or "demo_app_id",
        "has_cert": bool(settings.AGORA_APP_CERTIFICATE),
        "agent_uid": settings.AGORA_AGENT_RTC_UID,
        "default_voice": settings.AZURE_VOICE_NAME,
        "asr_provider": settings.ASR_PROVIDER,
        "tts_provider": settings.TTS_PROVIDER
    }
