import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import rtc_token, agora_agent, llm_proxy, tools, deal_state, session
from app.api.dialer import router as dialer_router
from app.routers import telemetry
from app.db.redis_client import redis_client
from app.db.postgres import init_db
from app.core.background import drain
from app.core.understanding import llm_understanding

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lively.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Lively Intelligence Core...")
    await redis_client.connect()
    await init_db()
    if settings.LLM_SECRET_IS_EPHEMERAL:
        logger.warning("LIVELY_LLM_SHARED_SECRET is not set; generated a per-process secret. "
                       "Agents started before a restart will be rejected. Set it in the environment for production.")
    if settings.SESSION_SECRET_IS_EPHEMERAL:
        logger.warning("SESSION_SECRET is not set; visitor sessions will not survive a restart.")
    if not (settings.SMTP_USER and settings.SMTP_PASSWORD):
        logger.warning("SMTP is not configured; invites are saved as local previews instead of being emailed.")
    yield
    await drain(3.0)
    logger.info("Shutting down Lively Intelligence Core...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Lively Real-Time Voice AI Sales Brain — Custom LLM Backend for Agora Conversational AI Engine",
    lifespan=lifespan
)

# CORS: the API authenticates with headers, not cookies, so credentials are never allowed cross-origin.
cors_origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in cors_origins else cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(session.router)
app.include_router(llm_proxy.router)
app.include_router(rtc_token.router)
app.include_router(agora_agent.router)
app.include_router(tools.router)
app.include_router(deal_state.router)
app.include_router(telemetry.router)
app.include_router(dialer_router)

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {
        "service": "Lively Intelligence Core",
        "version": settings.VERSION,
        "status": "online",
        "agora_connected": bool(settings.AGORA_APP_ID),
        "groq_connected": bool(settings.GROQ_API_KEY),
        "nvidia_connected": bool(settings.NVIDIA_NIM_API_KEY),
        "understanding": "llm" if llm_understanding.client else "rules",
        "endpoints": {
            "session": "/api/session",
            "openai_chat_completions": "/v1/chat/completions",
            "issue_rtc_token": "/api/agora/token",
            "agora_agent": "/api/agent/start",
            "deal_state": "/api/deal-state/{channel_name}",
            "tools_calendar": "/api/tools/book-demo",
            "tools_crm": "/api/tools/sync-crm",
            "tools_escalate": "/api/tools/escalate",
            "telemetry_websocket": "/api/ws/telemetry/{channel_name}?token=..."
        }
    }

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "healthy", "service": "lively-core"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
