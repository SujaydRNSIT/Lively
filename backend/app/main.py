import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import rtc_token, agora_agent, llm_proxy, tools, deal_state
from app.routers import telemetry
from app.db.redis_client import redis_client

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lively.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Lively Intelligence Core...")
    await redis_client.connect()
    yield
    logger.info("Shutting down Lively Intelligence Core...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Lively Real-Time Voice AI Sales Brain — Custom LLM Backend for Agora Conversational AI Engine",
    lifespan=lifespan
)

# CORS Configuration
cors_origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
if "*" in cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Mount API Routers
app.include_router(llm_proxy.router)
app.include_router(rtc_token.router)
app.include_router(agora_agent.router)
app.include_router(tools.router)
app.include_router(deal_state.router)
app.include_router(telemetry.router)

@app.get("/")
async def root():
    return {
        "service": "Lively Intelligence Core",
        "version": settings.VERSION,
        "status": "online",
        "agora_connected": bool(settings.AGORA_APP_ID),
        "groq_connected": bool(settings.GROQ_API_KEY),
        "nvidia_connected": bool(settings.NVIDIA_NIM_API_KEY),
        "endpoints": {
            "openai_chat_completions": "/v1/chat/completions",
            "issue_rtc_token": "/api/agora/token",
            "agora_agent": "/api/agora/start-agent",
            "deal_state": "/api/deal-state/{channel_name}",
            "tools_calendar": "/api/tools/book-demo",
            "tools_crm": "/api/tools/sync-crm",
            "tools_escalate": "/api/tools/escalate",
            "telemetry_websocket": "/api/ws/telemetry/{channel_name}"
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "lively-core"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
