import logging
from fastapi import APIRouter
from app.config import settings
from app.models.schemas import RtcTokenRequest, RtcTokenResponse
from app.services.agora_token import build_rtc_token

logger = logging.getLogger("lively.api.rtc_token")
router = APIRouter(prefix="/api", tags=["rtc_token"])

@router.post("/rtc-token", response_model=RtcTokenResponse)
@router.post("/agora/token", response_model=RtcTokenResponse)
async def generate_rtc_token(req: RtcTokenRequest):
    """
    Task 3.1: Given channel_name and uid, generate and return a short-lived Agora RTC token
    using App ID + App Certificate. The frontend calls this before joining a channel.
    """
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
