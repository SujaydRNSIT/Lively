import asyncio
import json
import logging
import time
from typing import Optional, Any
from fastapi import APIRouter, Request, Header
from fastapi.responses import StreamingResponse
from app.config import settings
from app.models.schemas import OpenAIChatCompletionRequest
from app.core.deal_state_engine import deal_state_engine
from app.core.llm_router import llm_router
from app.routers.telemetry import ws_manager

logger = logging.getLogger("lively.api.llm_proxy")
router = APIRouter(tags=["llm_proxy"])


def extract_text(content: Any) -> str:
    """Safely extract plain text from string or multi-part list of dicts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
            elif hasattr(item, "text"):
                parts.append(item.text)
        return " ".join(parts).strip()
    return str(content or "").strip()


async def handle_chat_completion(
    request: Request,
    body: OpenAIChatCompletionRequest,
    authorization: Optional[str] = None,
    x_agora_channel: Optional[str] = None
):
    logger.info(
        f"Incoming LLM request: model={body.model}, messages_count={len(body.messages)}, "
        f"stream={body.stream}, auth={'present' if authorization else 'none'}"
    )

    channel_name = x_agora_channel or request.query_params.get("channel", "lively-sales-room")
    deal_state = deal_state_engine.get_or_create(channel_name)

    # Extract user message safely
    user_utterance = ""
    for msg in reversed(body.messages):
        if msg.role == "user":
            user_utterance = extract_text(msg.content)
            break

    if user_utterance:
        logger.info(f"User utterance extracted: '{user_utterance}'")
        deal_state_engine.record_turn(channel_name, role="buyer", text=user_utterance)
        state_snapshot = deal_state.model_dump()
        # Fire-and-forget: don't block the hot path before LLM streaming
        asyncio.create_task(ws_manager.broadcast_state(channel_name, {
            "type": "TRANSCRIPT_TURN",
            "data": {
                "role": "buyer",
                "text": user_utterance,
                "deal_state": state_snapshot
            }
        }))
        asyncio.create_task(ws_manager.broadcast_state(channel_name, {
            "type": "DEAL_STATE_UPDATE",
            "data": state_snapshot
        }))

    # Prepare normalized messages for LLM
    raw_messages = [
        {"role": m.role, "content": extract_text(m.content)}
        for m in body.messages
    ]

    asyncio.create_task(ws_manager.broadcast_state(channel_name, {
        "type": "AGENT_STATUS",
        "data": {"status": "thinking"}
    }))

    async def token_generator():
        if settings.AGENT_RESPONSE_DELAY_SECONDS > 0:
            logger.info(f"Conversational pacing: waiting {settings.AGENT_RESPONSE_DELAY_SECONDS}s after user utterance before model responds...")
            await asyncio.sleep(settings.AGENT_RESPONSE_DELAY_SECONDS)

        # Emit custom metadata chunk (Task 4.1 Agora custom metadata protocol)
        meta_chunk = {
            "id": f"chatcmpl-{channel_name}-{int(time.time()*1000)}",
            "object": "chat.completion.custom_metadata",
            "created": int(time.time()),
            "model": body.model or "lively-sales-brain",
            "choices": [{
                "index": 0,
                "delta": {
                    "custom_metadata": {
                        "interruptable": True,
                        "deal_stage": str(deal_state.stage.value if hasattr(deal_state.stage, "value") else deal_state.stage)
                    }
                }
            }]
        }
        yield f"data: {json.dumps(meta_chunk)}\n\n"

        full_agent_response = []
        try:
            async for chunk in llm_router.stream_chat_completion(
                messages=raw_messages,
                deal_state=deal_state,
                channel_name=channel_name,
                model=body.model
            ):
                yield chunk
                if chunk.startswith("data:") and not chunk.startswith("data: [DONE]"):
                    try:
                        data_json = json.loads(chunk[5:].strip())
                        delta = data_json.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            full_agent_response.append(delta["content"])
                    except Exception:
                        pass
        finally:
            agent_text = "".join(full_agent_response).strip()
            if agent_text:
                logger.info(f"Agent response completed: '{agent_text[:80]}...'")
                deal_state_engine.record_turn(channel_name, role="agent", text=agent_text)
                final_snapshot = deal_state.model_dump()
                await ws_manager.broadcast_state(channel_name, {
                    "type": "TRANSCRIPT_TURN",
                    "data": {
                        "role": "agent",
                        "text": agent_text,
                        "deal_state": final_snapshot
                    }
                })
                await ws_manager.broadcast_state(channel_name, {
                    "type": "DEAL_STATE_UPDATE",
                    "data": final_snapshot
                })

    return StreamingResponse(
        token_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/v1/chat/completions")
async def chat_completions_v1(
    request: Request,
    body: OpenAIChatCompletionRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_agora_channel: Optional[str] = Header(default=None, alias="X-Agora-Channel-Name")
):
    return await handle_chat_completion(request, body, authorization, x_agora_channel)


@router.post("/chat/completions")
async def chat_completions_standard(
    request: Request,
    body: OpenAIChatCompletionRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_agora_channel: Optional[str] = Header(default=None, alias="X-Agora-Channel-Name")
):
    return await handle_chat_completion(request, body, authorization, x_agora_channel)
