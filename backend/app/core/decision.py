import logging
from app.models.schemas import DealState
from app.core.rag import rag_core

logger = logging.getLogger("lively.core.decision")

# Suggested responses per objection type. Kept consistent with the system prompt: no invented statistics.
REBUTTALS = {
    "pricing": "Ask what they're comparing against and their call volume, then match a plan: Starter at $199/month or a scoped Growth pilot.",
    "competitor": "Acknowledge the alternative, then contrast on interruption handling, Agora's real-time network and freedom to bring any LLM.",
    "latency": "Explain Agora's real-time network and native barge-in, then offer to prove it live in a demo.",
    "trust": "Explain the guardrails: answers come only from approved docs and anything uncertain goes to a human rep. Offer a pilot on their own FAQs.",
    "security": "Cover encryption in transit and the security review process; offer to bring in the security team for compliance specifics.",
    "product": "Pin down the exact workflow gap, confirm what's supported today, and be upfront about what isn't.",
}

MISSING_QUESTIONS = {
    "need": "Find out what problem they're trying to solve right now.",
    "budget": "When it fits, ask what budget range they're working with.",
    "authority": "When it fits, ask who else is involved in the decision.",
    "timeline": "When it fits, ask when they'd want this live.",
}


class DecisionEngine:
    """
    Decide layer: turns the current deal state (handoff, scheduling, objections, qualification gaps)
    into one next-best-action for the agent.
    """
    def evaluate_next_action(self, state: DealState) -> str:
        if state.escalation:
            return "Tell the buyer a human account executive is joining with the full context; stop pitching and don't re-ask questions."

        if state.slot_conflict:
            alternatives = ", ".join(state.slot_conflict.get("alternatives") or []) or "the next open slots"
            return f"Say the requested time is unavailable ({state.slot_conflict.get('reason')}) and offer: {alternatives}."

        demo = state.scheduled_demo if state.scheduled_demo and state.scheduled_demo.get("status") == "CONFIRMED" else None
        if demo and not demo.get("email"):
            return f"Demo confirmed for {demo['time']}. Ask for the best email to send the invite."

        if state.pending_demo_request:
            slots = ", ".join(state.available_slots[:3]) or "the next open slots"
            return f"Offer open demo slots: {slots}."

        if state.active_objections:
            latest = state.active_objections[-1]
            return REBUTTALS.get(latest.type, "Address the concern directly, then check it landed.")

        if demo:
            return f"Demo confirmed for {demo['time']}. Confirm who should attend and what they want to see."

        missing = [d for d in ("need", "budget", "authority", "timeline") if getattr(state.bant, d).get("status") != "Identified"]
        if missing:
            return MISSING_QUESTIONS[missing[0]]
        return "Lead is qualified. Propose a demo using the open slots."

    def retrieve_context(self, user_query: str) -> str:
        hits = rag_core.retrieve(user_query, top_k=2)
        if not hits:
            return "No specific battlecard snippet found."
        return "\n\n".join([f"[{h['title']}]\n{h['content']}" for h in hits])

decision_engine = DecisionEngine()
