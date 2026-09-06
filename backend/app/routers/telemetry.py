import json
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from app.core.deal_state_engine import deal_state_engine
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
            for ws in self.active_connections[channel_name]:
                try:
                    await ws.send_text(data_str)
                except Exception:
                    dead.add(ws)
            for ws in dead:
                self.active_connections[channel_name].discard(ws)

ws_manager = ConnectionManager()

@router.websocket("/ws/telemetry/{channel_name}")
async def websocket_telemetry_endpoint(websocket: WebSocket, channel_name: str):
    await ws_manager.connect(channel_name, websocket)
    initial_state = deal_state_engine.get_or_create(channel_name)
    await websocket.send_text(json.dumps({
        "type": "DEAL_STATE_SNAPSHOT",
        "data": initial_state.model_dump()
    }))

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
                    deal_state_engine.resolve_objection(channel_name, obj_id)
                    updated = deal_state_engine.get_state(channel_name)
                    if updated:
                        await ws_manager.broadcast_state(channel_name, {
                            "type": "DEAL_STATE_UPDATE",
                            "data": updated.model_dump()
                        })
    except WebSocketDisconnect:
        ws_manager.disconnect(channel_name, websocket)
    except Exception as e:
        logger.warning(f"WS error: {e}")
        ws_manager.disconnect(channel_name, websocket)

@router.get("/telemetry/latency-stats")
async def get_latency_stats():
    """
    Task 5.3: Returns real-time latency analytics (TTFT p50/p95, model distribution) for hackathon evidence.
    """
    from app.core.llm_router import latency_tracker
    return {
        "status": "success",
        "data": latency_tracker.get_stats()
    }

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
