import json
import logging
from typing import Dict, Optional, Set
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from app.core.deal_state_engine import deal_state_engine
from app.core.security import parse_session_token
from app.scripts.ingest_docs import DOCUMENTS_SOURCE

logger = logging.getLogger("lively.telemetry")
router = APIRouter(prefix="/api", tags=["telemetry"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, channel_name: str, websocket: WebSocket):
        await websocket.accept()
        if channel_name not in self.active_connections:
            self.active_connections[channel_name] = set()
        self.active_connections[channel_name].add(websocket)
        logger.info(f"WebSocket client connected to channel: {channel_name}")

    def disconnect(self, channel_name: str, websocket: WebSocket):
        if channel_name in self.active_connections:
            self.active_connections[channel_name].discard(websocket)
            if not self.active_connections[channel_name]:
                del self.active_connections[channel_name]

    async def broadcast_state(self, channel_name: str, payload: dict):
        if channel_name in self.active_connections:
            data_str = json.dumps(payload)
            dead = set()
            for ws in list(self.active_connections[channel_name]):
                try:
                    await ws.send_text(data_str)
                except Exception:
                    dead.add(ws)
            for ws in dead:
                self.active_connections.get(channel_name, set()).discard(ws)

ws_manager = ConnectionManager()

@router.websocket("/ws/telemetry/{channel_name}")
async def websocket_telemetry_endpoint(websocket: WebSocket, channel_name: str, token: Optional[str] = Query(default=None)):
    # Browsers can't set headers on WebSockets, so the session token travels as ?token=
    if parse_session_token(token) != channel_name:
        await websocket.close(code=4401)
        return
    await ws_manager.connect(channel_name, websocket)
    initial_state = deal_state_engine.get_or_create(channel_name)
    await websocket.send_text(json.dumps({"type": "DEAL_STATE_SNAPSHOT", "data": initial_state.model_dump()}))

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            action = msg.get("action")
            if action == "PING":
                await websocket.send_text(json.dumps({"type": "PONG"}))
            elif action == "RESOLVE_OBJECTION":
                obj_id = msg.get("objection_id")
                if obj_id:
                    updated = deal_state_engine.resolve_objection(channel_name, obj_id)
                    await ws_manager.broadcast_state(channel_name, {"type": "DEAL_STATE_UPDATE", "data": updated.model_dump()})
    except WebSocketDisconnect:
        ws_manager.disconnect(channel_name, websocket)
    except Exception as e:
        logger.warning(f"WS error: {e}")
        ws_manager.disconnect(channel_name, websocket)

@router.get("/telemetry/latency-stats")
async def get_latency_stats():
    """
    Task 5.3: Measured latency (TTFT p50/p95, model distribution). Values are null until turns are measured.
    """
    from app.core.llm_router import latency_tracker
    from app.core.understanding import llm_understanding
    stats = latency_tracker.get_stats()
    stats["understanding"] = {"mode": "llm" if llm_understanding.client else "rules", **llm_understanding.stats}
    return {"status": "success", "data": stats}

@router.get("/knowledge")
async def get_knowledge_base():
    docs = [
        {
            "doc_id": d["doc_id"],
            "title": d["title"],
            "category": d["category"],
            "content": d["content"],
            "keywords": d.get("keywords", [])
        }
        for d in DOCUMENTS_SOURCE
    ]
    return {"status": "success", "data": docs}
