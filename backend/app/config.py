import os
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
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"

    @model_validator(mode="after")
    def resolve_backend_public_url(self) -> "Settings":
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        # If BACKEND_PUBLIC_URL is localhost or empty, and we are running on Render, auto-use Render URL
        if self.BACKEND_PUBLIC_URL in ("http://localhost:8000", "http://localhost:8000/", "", None) and render_url:
            self.BACKEND_PUBLIC_URL = render_url.rstrip("/")
        else:
            self.BACKEND_PUBLIC_URL = (self.BACKEND_PUBLIC_URL or "").rstrip("/")
        return self

    # Internal / Client Auth
    LIVELY_API_KEY: str = "lively-session-secret-key-2026"
    LIVELY_LLM_SHARED_SECRET: str = "lively-custom-llm-secret-9988"

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

    # NVIDIA NIM Settings (Secondary / Reasoning / Fallback)
    NVIDIA_NIM_API_KEY: str = "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"
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_NIM_MODEL: str = "meta/llama-3.2-11b-vision-instruct"

    # Database & Cache Settings
    DATABASE_URL: Optional[str] = None
    REDIS_URL: Optional[str] = None
    VECTOR_DB_URL: Optional[str] = None

    # CORS
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,*"


    # Pinecone Vector DB
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "lively-rag"
    PINECONE_NAMESPACE: str = "knowledge-base"

    # Voice Turn Pacing (Pause in seconds after user finishes speaking before model responds)
    AGENT_RESPONSE_DELAY_SECONDS: float = 0.0

    # SMTP / Email Delivery Settings
    SMTP_HOST: Optional[str] = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = "anishhyd995@gmail.com"
    SMTP_PASSWORD: Optional[str] = "ybrpdrczcvdkqurr"
    SMTP_FROM: str = "Lively AI <anishhyd995@gmail.com>"
    SMTP_FROM_EMAIL: Optional[str] = "anishhyd995@gmail.com"
    SMTP_FROM_NAME: str = "Lively AI Solutions"
    SMTP_USE_TLS: bool = True



settings = Settings()
