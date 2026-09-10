"""
Post-Call Follow-Up Agent (Feature D).

After a call ends, one LLM call generates a personalised follow-up email draft.
The draft is stored in deal state and surfaced in the Cockpit.
The human explicitly clicks "Send" — the agent never sends autonomously.

Design decisions
----------------
- Uses the existing Groq client (already initialised in llm_router.py).
- If Groq is unavailable, falls back to a template-based draft (no failure modes).
- The call is made in a background task so it does not block the turn.
- The draft is stored in `deal_state.follow_up_draft` (new optional field).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger("lively.core.followup")


# --------------------------------------------------------------------------- #
# Follow-up draft builder                                                       #
# --------------------------------------------------------------------------- #

async def generate_follow_up_draft(deal_state: Any) -> Dict[str, Any]:
    """
    Generate a personalised follow-up email draft from the deal state.

    Returns a dict with keys: subject, body, to_email, generated_at, source.
    """
    contact = deal_state.contact_name or "there"
    company = deal_state.company if deal_state.company not in ("Prospective Client", "", None) else ""
    email   = deal_state.contact_email or ""
    stage   = str(getattr(deal_state.stage, "value", deal_state.stage))
    demo    = deal_state.scheduled_demo
    objections = [o.type for o in (deal_state.active_objections or [])]
    
    # Extract pain points from BANT or needs list
    pain_points = getattr(deal_state.bant.need, "get", lambda k, d=None: d)("pain_points") or []
    if not pain_points and getattr(deal_state, "needs", None):
        pain_points = deal_state.needs
    if isinstance(pain_points, list):
        pain_str = ", ".join(str(p) for p in pain_points[:4])
    else:
        pain_str = str(pain_points)

    # Try LLM-generated draft
    llm_draft = await _try_llm_draft(contact, company, stage, demo, objections, pain_str, deal_state)
    if llm_draft:
        return {
            "subject":      llm_draft["subject"],
            "body":         llm_draft["body"],
            "to_email":     email,
            "generated_at": time.time(),
            "source":       "llm",
        }

    # Fallback template
    return {
        "subject":      _template_subject(contact, company, demo),
        "body":         _template_body(contact, company, stage, demo, objections, pain_str),
        "to_email":     email,
        "generated_at": time.time(),
        "source":       "template",
    }


async def _try_llm_draft(
    contact: str,
    company: str,
    stage: str,
    demo: Optional[Dict[str, Any]],
    objections: list,
    pain_str: str,
    deal_state: Any,
) -> Optional[Dict[str, Any]]:
    """Attempt LLM generation; return None on any failure."""
    try:
        from groq import AsyncGroq
        if not settings.GROQ_API_KEY:
            return None

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        demo_line = f"Demo confirmed for {demo['time']}." if demo and demo.get("status") == "CONFIRMED" else "No demo booked yet."
        objection_line = f"Specific client concerns/objections: {', '.join(objections)}." if objections else "No blocking objections raised."
        pain_line = f"Client's stated pain points & challenges: {pain_str}." if pain_str else ""
        
        users_count = getattr(deal_state, "users", None)
        users_line = f"Team size / seats: {users_count} reps/users." if users_count else ""
        
        competitor = getattr(deal_state, "competitor_mentioned", None)
        competitor_line = f"Current tool/competitor mentioned: {competitor}." if competitor else ""

        timeline = getattr(deal_state, "timeline", None)
        timeline_line = f"Decision timeline: {timeline}." if timeline else ""

        transcript_turns = getattr(deal_state, "transcript", []) or []
        recent_buyer_lines = [t.content for t in transcript_turns if getattr(t, "role", None) == "buyer"][-5:]
        buyer_context = f"What the client said in call: {' // '.join(recent_buyer_lines)}" if recent_buyer_lines else ""

        prompt = (
            f"Write a brief, warm, highly personalized post-call follow-up email from Lively AI to this specific prospective client.\n"
            f"CRITICAL REQUIREMENT: Customize this email completely around THIS client's individual situation, pain points, company, and conversation context. "
            f"Never write generic marketing copy or reuse assumptions from other clients.\n\n"
            f"Client Name: {contact}\n"
            f"Client Company: {company or 'their team'}\n"
            f"Deal Stage: {stage}\n"
            f"{users_line}\n"
            f"{pain_line}\n"
            f"{objection_line}\n"
            f"{competitor_line}\n"
            f"{timeline_line}\n"
            f"{demo_line}\n"
            f"{buyer_context}\n\n"
            f"Email Guidelines:\n"
            f"- Address {contact} directly and naturally.\n"
            f"- In the first paragraph, reference what they specifically described regarding {company or 'their team'}'s situation.\n"
            f"- In the second paragraph, explain how Lively directly solves their unique situation and problem.\n"
            f"- Conclude with a clear next step (if demo confirmed, acknowledge the scheduled time; if not, suggest a short walkthrough).\n"
            f"- Tone: Consultative, concise, respectful, authentic (no bullet points, max 2 short paragraphs).\n"
            f"- Return ONLY valid JSON with keys 'subject' and 'body'."
        )

        response = await client.chat.completions.create(
            model       = settings.GROQ_MODEL,
            messages    = [{"role": "user", "content": prompt}],
            stream      = False,
            temperature = 0.6,
            max_tokens  = 250,
            response_format = {"type": "json_object"},
        )
        import json
        content = response.choices[0].message.content or ""
        data    = json.loads(content)
        if "subject" in data and "body" in data:
            return data
        return None
    except Exception as e:
        logger.warning(f"[FollowUp] Groq LLM draft failed: {e}. Trying secondary LLM...")
        try:
            import httpx
            if settings.NVIDIA_NIM_API_KEY:
                headers = {"Authorization": f"Bearer {settings.NVIDIA_NIM_API_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": settings.NVIDIA_NIM_MODEL,
                    "messages": [
                        {"role": "system", "content": "You write concise, warm, highly personalized sales follow-up emails tailored specifically to each client's unique situation. Respond ONLY with valid JSON with keys 'subject' and 'body'."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.6,
                    "max_tokens": 250,
                }
                async with httpx.AsyncClient(timeout=10) as http_client:
                    res = await http_client.post(f"{settings.NVIDIA_NIM_BASE_URL}/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200:
                        raw_text = res.json()["choices"][0]["message"]["content"]
                        import re
                        m = re.search(r"\{.*\}", raw_text, re.DOTALL)
                        if m:
                            import json
                            data = json.loads(m.group(0))
                            if "subject" in data and "body" in data:
                                return data
        except Exception as nim_err:
            logger.warning(f"[FollowUp] Secondary LLM draft failed: {nim_err}")
        return None


def _template_subject(contact: str, company: str, demo: Optional[Dict[str, Any]]) -> str:
    if demo and demo.get("status") == "CONFIRMED":
        return f"Your Lively demo is confirmed — {demo.get('time', 'soon')}"
    if company:
        return f"Following up on our conversation — Lively for {company}"
    return f"Great talking with you, {contact} — next steps from Lively"


def _template_body(
    contact: str,
    company: str,
    stage: str,
    demo: Optional[Dict[str, Any]],
    objections: list,
    pain_str: str,
) -> str:
    greeting = f"Hi {contact},"
    if demo and demo.get("status") == "CONFIRMED":
        opening = (
            f"Thanks for the conversation today. Your demo with a Solutions Architect "
            f"is confirmed for {demo['time']} — the video room link is in the calendar invite."
        )
    elif stage in ("discovery", "qualification"):
        opening = (
            "Thanks for taking the time to chat. It was great to learn more about "
            f"{'what ' + company + ' is working through' if company else 'your situation'}."
        )
    else:
        opening = "Thanks for the conversation — here's a quick recap of where we landed."

    middle = ""
    if pain_str:
        middle = f"\nYou mentioned {pain_str} as a key area. Lively's voice agents address this directly with real-time qualification and instant CRM sync, so your team spends time on warm leads, not cold follow-ups."
    elif objections:
        middle = f"\nI know {objections[0]} was top of mind. Happy to send over a one-pager that walks through how other teams in your space have handled it."

    if demo and demo.get("status") == "CONFIRMED":
        cta = "Looking forward to showing you Lively in action on your own workflow."
    else:
        cta = "If you'd like to see it live, I can hold a slot with one of our Solutions Architects — just reply here."

    return f"{greeting}\n\n{opening}{middle}\n\n{cta}\n\nBest,\nThe Lively Team"
