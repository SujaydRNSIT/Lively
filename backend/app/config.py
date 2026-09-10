import os
import secrets
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App Settings
    PROJECT_NAME: str = "Lively - Real-Time Voice AI Sales Agent"
    VERSION: str = "1.1.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"

    @model_validator(mode="after")
    def resolve_backend_public_url(self) -> "Settings":
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        if self.BACKEND_PUBLIC_URL in ("http://localhost:8000", "http://localhost:8000/", "", None) and render_url:
            self.BACKEND_PUBLIC_URL = render_url.rstrip("/")
        else:
            self.BACKEND_PUBLIC_URL = (self.BACKEND_PUBLIC_URL or "").rstrip("/")
        if self.NVIDIA_NIM_MODEL in ("meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct", "meta/llama-3.3-70b-instruct", "", None):
            self.NVIDIA_NIM_MODEL = "meta/llama-3.2-11b-vision-instruct"
        # Secrets are never hardcoded. When unset, generate per-process values so the app still runs on a
        # single instance; main.py logs a warning telling operators to pin them in the environment.
        if not self.LIVELY_LLM_SHARED_SECRET:
            self.LIVELY_LLM_SHARED_SECRET = secrets.token_urlsafe(32)
            self.LLM_SECRET_IS_EPHEMERAL = True
        if not self.SESSION_SECRET:
            self.SESSION_SECRET = secrets.token_urlsafe(32)
            self.SESSION_SECRET_IS_EPHEMERAL = True
        return self

    # Security
    # Agora sends this as "Authorization: Bearer <secret>" when it calls /v1/chat/completions.
    LIVELY_LLM_SHARED_SECRET: str = ""
    # Set to false only if your Agora agent cannot send llm.api_key (the endpoint is then open to anyone).
    REQUIRE_LLM_SECRET: bool = True
    # HMAC key for per-visitor session tokens.
    SESSION_SECRET: str = ""
    SESSION_TTL_SECONDS: int = 86400
    LLM_SECRET_IS_EPHEMERAL: bool = False
    SESSION_SECRET_IS_EPHEMERAL: bool = False

    # Rate limits
    RATE_LIMIT_SESSIONS_PER_HOUR: int = 30
    RATE_LIMIT_CHAT_PER_MINUTE: int = 30
    EMAILS_PER_CHANNEL_PER_HOUR: int = 3

    # Agora Credentials
    AGORA_APP_ID: str = ""
    AGORA_APP_CERTIFICATE: str = ""
    AGORA_REST_KEY: str = ""
    AGORA_REST_SECRET: str = ""
    AGORA_AGENT_RTC_UID: int = 9999

    # ASR / TTS Voice Engine Settings
    ASR_PROVIDER: str = "ares"
    TTS_PROVIDER: str = "elevenlabs"
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"
    ELEVENLABS_API_KEY: str = ""
    AZURE_VOICE_NAME: str = "en-US-JennyNeural"

    # Groq Settings (Primary low-latency LLM)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    # Small, fast model that turns each buyer utterance into structured deal signals (intent, entities,
    # objections). If it does not answer within the timeout, the rule-based extractor is used instead.
    EXTRACTION_MODEL: str = "llama-3.1-8b-instant"
    EXTRACTION_TIMEOUT_SECONDS: float = 0.6

    # NVIDIA NIM Settings (fallback when Groq fails before producing any tokens)
    NVIDIA_NIM_API_KEY: str = ""
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_NIM_MODEL: str = "meta/llama-3.2-11b-vision-instruct"

    # Database & Cache Settings
    DATABASE_URL: Optional[str] = None
    REDIS_URL: Optional[str] = None
    VECTOR_DB_URL: Optional[str] = None

    # CORS (comma separated). The API authenticates with headers, never cookies, so credentials stay off.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # Pinecone Vector DB
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "lively-rag"
    PINECONE_NAMESPACE: str = "knowledge-base"

    # Pacing / Latency controls (0 = respond as soon as the model streams)
    AGENT_RESPONSE_DELAY_SECONDS: float = 0.0

    # Calendar & meetings
    # Each booking gets its own shareable room on this host, so the buyer and the AE land in the same room.
    MEETING_ROOM_BASE_URL: str = "https://meet.jit.si"
    CALENDAR_UTC_OFFSET_HOURS: int = -5
    CALENDAR_TZ_LABEL: str = "EST"
    CALENDAR_WORKING_DAYS: str = "mon,tue,wed,thu,fri"
    CALENDAR_SLOT_TIMES: str = "10:00,14:00,16:00"
    BUSINESS_HOURS_START: int = 9
    BUSINESS_HOURS_END: int = 17

    # CRM (optional HubSpot private-app token; in-memory CRM is always on)
    HUBSPOT_ACCESS_TOKEN: str = ""

    # Human handoff notification (optional): the AE inbox that receives the context summary
    ESCALATION_NOTIFY_EMAIL: Optional[str] = None

    # SMTP / Email Delivery Settings (no defaults: configure in the environment)
    SMTP_HOST: Optional[str] = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "Lively AI <no-reply@example.com>"
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "Lively AI Solutions"
    SMTP_USE_TLS: bool = True


settings = Settings()
