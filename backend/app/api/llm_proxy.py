import asyncio
import json
import logging
import time
from typing import Optional, Any
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
from app.config import settings
from app.models.schemas import OpenAIChatCompletionRequest
from app.core.deal_state_engine import deal_state_engine
from app.core.llm_router import llm_router
from app.core.understanding import llm_understanding
from app.core.security import is_valid_llm_secret, parse_session_token, enforce_rate_limit
from app.core.background import spawn
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


def authorize_chat(authorization: Optional[str], session_token: Optional[str], channel_param: Optional[str]) -> str:
    """
    Two callers are allowed:
      * Agora's ConvoAI engine, which sends the shared secret as a Bearer token (channel comes from the URL).
      * The visitor's browser (sandbox and scripted demo), which sends its own session token.
    """
    if is_valid_llm_secret(authorization):
        if not channel_param:
            raise HTTPException(status_code=400, detail="Missing channel.")
        return channel_param
    session_channel = parse_session_token(session_token)
    if session_channel:
        if channel_param and channel_param != session_channel:
            raise HTTPException(status_code=403, detail="This session cannot write to that channel.")
        enforce_rate_limit(f"chat:{session_channel}", settings.RATE_LIMIT_CHAT_PER_MINUTE, 60, "Too many messages. Please slow down.")
        return session_channel
    if not settings.REQUIRE_LLM_SECRET:
        return channel_param or "lively-sales-room"
    logger.warning("Rejected /v1/chat/completions without a valid Agora secret or visitor session. "
                   "If your Agora agent cannot send llm.api_key, set REQUIRE_LLM_SECRET=false.")
    raise HTTPException(status_code=401, detail="Unauthorized.")


async def handle_chat_completion(
    request: Request,
    body: OpenAIChatCompletionRequest,
    authorization: Optional[str] = None,
    x_agora_channel: Optional[str] = None,
    x_lively_session: Optional[str] = None
):
    started = time.perf_counter()
    channel_name = authorize_chat(authorization, x_lively_session, x_agora_channel or request.query_params.get("channel"))
    logger.info(f"Incoming LLM request: channel={channel_name}, messages_count={len(body.messages)}, stream={body.stream}")
    deal_state = deal_state_engine.get_or_create(channel_name)

    # Extract user message safely
    user_utterance = ""
    for msg in reversed(body.messages):
        if msg.role == "user":
            user_utterance = extract_text(msg.content)
            break

    # Strip accumulated prior sentences if ASR buffer prepended previous utterances
    if user_utterance and deal_state and deal_state.transcript:
        recent_buyer_turns = [t.content.strip() for t in reversed(deal_state.transcript) if t.role == "buyer"]
        for past_text in recent_buyer_turns[:3]:
            if past_text and past_text in user_utterance and len(user_utterance) > len(past_text) + 2:
                user_utterance = user_utterance.replace(past_text, "").strip(" .,\n-")

    # Check for rapid duplicate turns (debounce within 2.0s)
    is_duplicate = False
    now = time.time()
    if deal_state.transcript:
        last_turn = deal_state.transcript[-1]
        if last_turn.role == "buyer" and last_turn.content.strip().lower() == user_utterance.strip().lower() and (now - last_turn.timestamp) < 2.0:
            is_duplicate = True

    if user_utterance and not is_duplicate:
        logger.info(f"User utterance extracted: '{user_utterance}'")
        # Structured understanding from a small fast model, bounded by EXTRACTION_TIMEOUT_SECONDS.
        # None means the rule-based extractor handles this turn.
        understanding = await llm_understanding.extract(user_utterance, deal_state)
        deal_state_engine.record_turn(channel_name, role="buyer", text=user_utterance, understanding=understanding)
        state_snapshot = deal_state.model_dump()
        spawn(ws_manager.broadcast_state, channel_name, {
            "type": "TRANSCRIPT_TURN",
            "data": {"role": "buyer", "text": user_utterance, "deal_state": state_snapshot}
        })
        spawn(ws_manager.broadcast_state, channel_name, {"type": "DEAL_STATE_UPDATE", "data": state_snapshot})

    # Prepare normalized messages for LLM
    raw_messages = [
        {"role": m.role, "content": extract_text(m.content)}
        for m in body.messages
    ]
    if raw_messages and user_utterance:
        for m in reversed(raw_messages):
            if m["role"] == "user":
                m["content"] = user_utterance
                break

    # If the payload only has the latest turn, rebuild multi-turn context from the transcript
    if len(raw_messages) <= 1 and deal_state.transcript:
        raw_messages = [
            {"role": "assistant" if t.role == "agent" else "user", "content": t.content}
            for t in deal_state.transcript[-8:]
        ]

    spawn(ws_manager.broadcast_state, channel_name, {"type": "AGENT_STATUS", "data": {"status": "thinking"}})

    async def token_generator():
        if settings.AGENT_RESPONSE_DELAY_SECONDS > 0:
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
                model=body.model,
                request_started_at=started
            ):
                yield chunk
                if chunk.startswith("data:") and not chunk.startswith("data: [DONE]"):
                    try:
                        data_json = json.loads(chunk[5:].strip())
                        delta = data_json.get("choices", [{}])[0].get("delta", {})
                        if delta.get("content"):
                            full_agent_response.append(delta["content"])
                    except Exception:
                        pass
        finally:
            agent_text = "".join(full_agent_response).strip()
            if agent_text:
                logger.info(f"Agent response completed: '{agent_text[:80]}...'")
                deal_state_engine.record_turn(channel_name, role="agent", text=agent_text)
                final_snapshot = deal_state.model_dump()
                spawn(ws_manager.broadcast_state, channel_name, {
                    "type": "TRANSCRIPT_TURN",
                    "data": {"role": "agent", "text": agent_text, "deal_state": final_snapshot}
                })
                spawn(ws_manager.broadcast_state, channel_name, {"type": "DEAL_STATE_UPDATE", "data": final_snapshot})

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
    x_agora_channel: Optional[str] = Header(default=None, alias="X-Agora-Channel-Name"),
    x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")
):
    return await handle_chat_completion(request, body, authorization, x_agora_channel, x_lively_session)


@router.post("/chat/completions")
async def chat_completions_standard(
    request: Request,
    body: OpenAIChatCompletionRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_agora_channel: Optional[str] = Header(default=None, alias="X-Agora-Channel-Name"),
    x_lively_session: Optional[str] = Header(default=None, alias="X-Lively-Session")
):
    return await handle_chat_completion(request, body, authorization, x_agora_channel, x_lively_session)
