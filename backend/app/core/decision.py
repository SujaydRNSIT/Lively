import logging
from typing import Dict, Any, List
from app.models.schemas import DealState, DealStageEnum
from app.core.rag import rag_core

logger = logging.getLogger("lively.core.decision")

class DecisionEngine:
    """
    Decide layer: Consults sales playbook policy, objection matrix, and RAG knowledge
    to determine Next-Best-Action and contextual recommendations for each conversational turn.
    """
    def evaluate_next_action(self, state: DealState) -> str:
        # Priority 1: Active Objections
        if state.active_objections:
            top_obj = state.active_objections[0]
            if top_obj.category == "pricing":
                return "Present 40-60% TCO advantage and propose Starter ($199/mo) or Growth ($699/mo) evaluation."
            elif top_obj.category == "competitor":
                return "Emphasize Agora SD-RTN infrastructure quality and freedom to swap custom LLM brains over OpenAI/Twilio lock-in."
            elif top_obj.category == "latency":
                return "Explain that Agora WebRTC + Groq LPU achieves true sub-300ms glass-to-glass latency with instant barge-in."
            elif top_obj.category == "security":
                return "Highlight SOC2 Type II, HIPAA compliance, and sovereign NVIDIA NIM on-premise deployment."

        # Priority 2: Stage Progression & Qualification
        if state.stage == DealStageEnum.DISCOVERY:
            if state.bant.need.get("status") == "Identified":
                return "Transition to Value Pitch: showcase Agora Conversational AI architecture."
            return "Ask targeted discovery question about current real-time voice latency and interruption challenges."

        elif state.stage == DealStageEnum.QUALIFICATION:
            if state.bant.authority.get("status") != "Identified":
                return "Confirm decision maker role and evaluation committee."
            if state.bant.timeline.get("status") != "Identified":
                return "Determine go-live target date or evaluation timeline."
            return "Move to Value Pitch and demo proposal."

        elif state.stage == DealStageEnum.OBJECTION_HANDLING:
            return "Address the active objection using the relevant battlecard, then steer toward demo scheduling."

        elif state.stage == DealStageEnum.DEMO_SCHEDULING:
            if not state.scheduled_demo:
                return "Confirm date/time for demo and capture prospect's email address."
            time_str = state.scheduled_demo.get("time", "the requested time")
            return f"Reiterate demo details confirmed for {time_str} and offer to dispatch calendar invite."

        elif state.stage == DealStageEnum.ESCALATED:
            return "Reassure the buyer that a live human Account Executive is connecting on the hot-transfer bridge."

        elif state.stage == DealStageEnum.CLOSED:
            return "Thank the buyer and confirm next steps for onboarding."

        return "Qualify buyer requirements and introduce Agora Conversational AI capabilities."

    def retrieve_context(self, user_query: str) -> str:
        hits = rag_core.retrieve(user_query, top_k=2)
        if not hits:
            return "No specific battlecard snippet found."
        return "\n\n".join([f"[{h['title']}]\n{h['content']}" for h in hits])

decision_engine = DecisionEngine()
