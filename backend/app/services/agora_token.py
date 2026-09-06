import logging
import time
from typing import Dict, Any
from app.config import settings

logger = logging.getLogger("lively.services.agora_token")

def build_rtc_token(
    app_id: str,
    app_cert: str,
    channel_name: str,
    uid: int | str,
    role: int = 1,
    privilege_expire_seconds: int = 86400
) -> str:
    if not app_id or not app_cert:
        return f"demo_token_channel_{channel_name}_uid_{uid}"

    try:
        from agora_token_builder import RtcTokenBuilder
        expire_ts = int(time.time()) + privilege_expire_seconds
        token = RtcTokenBuilder.buildTokenWithUid(
            app_id,
            app_cert,
            channel_name,
            int(uid),
            role,
            expire_ts
        )
        return token
    except Exception as e:
        logger.exception(f"Token build failed: {e}")
        return f"fallback_token_channel_{channel_name}_uid_{uid}"
