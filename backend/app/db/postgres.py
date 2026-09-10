import logging
import json
import time
from typing import AsyncGenerator, Optional, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, Float, Text, Boolean, JSON, DateTime
from app.config import settings

logger = logging.getLogger("lively.db.postgres")

Base = declarative_base()

# SQLAlchemy ORM Models for Deal State & Escalation Queue
class DealStateTable(Base):
    __tablename__ = "deal_states"

    channel_name = Column(String(128), primary_key=True, index=True)
    session_id = Column(String(128), index=True)
    company = Column(String(256), default="Prospective Client")
    contact_name = Column(String(128), default="Prospect")
    decision_maker = Column(String(128), default="Unknown")
    needs = Column(JSON, default=list)
    users = Column(Integer, default=10)
    budget = Column(String(64), default="$50,000 ARR")
    timeline = Column(String(64), default="Q1")
    competitor_mentioned = Column(String(128), nullable=True)
    objections = Column(JSON, default=list)
    stage = Column(String(64), default="discovery")
    next_best_action = Column(Text, default="")
    change_log = Column(JSON, default=list)
    full_state = Column(JSON, default=dict)
    updated_at = Column(Float, default=time.time)

class EscalationQueueTable(Base):
    __tablename__ = "escalation_queue"

    id = Column(String(128), primary_key=True)
    channel_name = Column(String(128), index=True)
    reason = Column(Text)
    urgency = Column(String(32), default="Immediate")
    deal_state_snapshot = Column(JSON)
    transcript_snapshot = Column(JSON)
    created_at = Column(Float, default=time.time)
    status = Column(String(32), default="QUEUED") # QUEUED, ASSIGNED, RESOLVED

DATABASE_URL = settings.DATABASE_URL or "sqlite+aiosqlite:///./lively_local.db"

# Automatically normalize PostgreSQL URLs for asyncpg driver
connect_args = {}
if DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1).replace("postgres://", "postgresql+asyncpg://", 1)
    if "sslmode" in DATABASE_URL:
        import urllib.parse
        parsed = urllib.parse.urlparse(DATABASE_URL)
        q = urllib.parse.parse_qs(parsed.query)
        q.pop("sslmode", None)
        DATABASE_URL = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(q, doseq=True)))
    
    # Handle direct Supabase IPv6-only DNS resolution failure on IPv4 networks
    import re, socket
    m = re.search(r"@db\.([a-z0-9]+)\.supabase\.co", DATABASE_URL)
    if m:
        ref = m.group(1)
        try:
            socket.getaddrinfo(f"db.{ref}.supabase.co", 5432)
        except Exception:
            # Route to IPv4 pooler for this project (Seoul ap-northeast-2)
            DATABASE_URL = re.sub(r"://([^:]+):", f"://\\1.{ref}:", DATABASE_URL, count=1)
            DATABASE_URL = DATABASE_URL.replace(f"db.{ref}.supabase.co", "aws-0-ap-northeast-2.pooler.supabase.com")
            logger.info("[Database] Direct Supabase host IPv6-only; routed to IPv4 pooler.")

    if "supabase.co" in DATABASE_URL or "pooler.supabase.com" in DATABASE_URL or "neon.tech" in DATABASE_URL:
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

engine = None
async_session_factory = None

try:
    engine = create_async_engine(
        DATABASE_URL,
        connect_args=connect_args,
        echo=False,
        future=True,
        pool_pre_ping=True
    )
    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")

async def init_db():
    if engine:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize DB tables: {e}")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        yield None
        return
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
