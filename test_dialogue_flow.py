import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from app.core.llm_router import LLMRouter
from app.core.deal_state_engine import deal_state_engine

TURNS = [
    "Hey, Lively. Am I audible?",
    "I wanna increase my sales.",
    "It's impressive.",
    "Isn't it too costly?",
    "And this is this very yes. It's a around one thousand.",
    "Follow-up"
]

async def run_dialogue():
    router = LLMRouter()
    channel = "test_conversation_anomaly"
    deal_state_engine.reset_state(channel)
    state = deal_state_engine.get_or_create(channel)

    print("=== TESTING EXACT USER CONVERSATION FLOW ===")
    history = []
    
    for user_turn in TURNS:
        deal_state_engine.record_turn(channel, "buyer", user_turn)
        history.append({"role": "user", "content": user_turn})
        
        response_text = ""
        async for chunk in router.stream_chat_completion(history, state, channel):
            for line in chunk.split("\n"):
                line = line.strip()
                if line.startswith("data:") and not line.endswith("[DONE]"):
                    try:
                        payload = json.loads(line[5:].strip())
                        delta = payload.get("choices", [{}])[0].get("delta", {})
                        response_text += delta.get("content", "")
                    except Exception:
                        pass
                        
        response_text = response_text.strip()
        deal_state_engine.record_turn(channel, "agent", response_text)
        history.append({"role": "assistant", "content": response_text})
        
        print(f"\n[Buyer]:  {user_turn}", flush=True)
        print(f"[Lively]: {response_text}", flush=True)

if __name__ == "__main__":
    asyncio.run(run_dialogue())
