"""
Access control for a public demo:
  * Per-visitor session tokens (HMAC-signed, bound to one server-generated channel) so each visitor can
    only read and act on their own conversation.
  * The shared secret Agora presents when it calls the custom LLM endpoint.
  * Small in-memory rate limits for session creation, chat turns and outbound email.
"""
import base64
import hashlib
import hmac
import time
import uuid
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from fastapi import Header, HTTPException, Request

from app.config import settings


def _sign(payload: str) -> str:
    return hmac.new(settings.SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def new_channel_name() -> str:
    return f"lively-{uuid.uuid4().hex[:12]}"


def issue_session_token(channel_name: str) -> Tuple[str, int]:
    expires_at = int(time.time()) + settings.SESSION_TTL_SECONDS
    payload = f"{channel_name}|{expires_at}"
    raw = f"{payload}|{_sign(payload)}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("="), expires_at


def parse_session_token(token: Optional[str]) -> Optional[str]:
    """Return the channel a token grants access to, or None if it is missing, forged or expired."""
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode((token + "=" * (-len(token) % 4)).encode()).decode()
        channel, expires_at, signature = raw.rsplit("|", 2)
        if not hmac.compare_digest(signature, _sign(f"{channel}|{expires_at}")):
            return None
        if int(expires_at) < time.time():
            return None
        return channel
    except Exception:
        return None


def require_channel_access(channel_name: str, token: Optional[str]) -> None:
    if not channel_name or parse_session_token(token) != channel_name:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid session for this channel. Create one with POST /api/session.",
        )


async def channel_path_access(
    channel_name: str,
    x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session"),
) -> str:
    """Dependency for routes with a {channel_name} path parameter."""
    require_channel_access(channel_name, x_lively_session)
    return channel_name


def is_valid_llm_secret(authorization: Optional[str]) -> bool:
    if not authorization:
        return False
    token = authorization.split(" ", 1)[1] if authorization.lower().startswith("bearer ") else authorization
    return hmac.compare_digest(token.strip(), settings.LIVELY_LLM_SHARED_SECRET)


class RateLimiter:
    """Sliding-window limiter. In-memory, so limits apply per process."""

    def __init__(self):
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    def reset(self):
        self._hits.clear()


rate_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(key: str, limit: int, window_seconds: float, detail: str = "Too many requests. Please slow down.") -> None:
    if not rate_limiter.allow(key, limit, window_seconds):
        raise HTTPException(status_code=429, detail=detail)
