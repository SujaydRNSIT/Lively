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
    pain_points = getattr(deal_state.bant.need, "get", lambda k, d=None: d)("pain_points") or []
    if isinstance(pain_points, list):
        pain_str = ", ".join(pain_points[:3])
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
        objection_line = f"Open objections: {', '.join(objections)}." if objections else "No open objections."
        pain_line = f"Pain points mentioned: {pain_str}." if pain_str else ""

        prompt = (
            f"Write a brief, warm post-call follow-up email from Lively AI to a prospect.\n"
            f"Prospect name: {contact}\n"
            f"Company: {company or 'unknown'}\n"
            f"Deal stage: {stage}\n"
            f"{demo_line}\n"
            f"{objection_line}\n"
            f"{pain_line}\n"
            f"Rules: no bullet points; two to three short paragraphs; conversational tone; "
            f"end with one clear next-step sentence. "
            f"Return JSON with keys 'subject' and 'body' only."
        )

        response = await client.chat.completions.create(
            model       = settings.GROQ_MODEL,
            messages    = [{"role": "user", "content": prompt}],
            stream      = False,
            temperature = 0.6,
            max_tokens  = 350,
            response_format = {"type": "json_object"},
        )
        import json
        content = response.choices[0].message.content or ""
        data    = json.loads(content)
        if "subject" in data and "body" in data:
            return data
        return None
    except Exception as e:
        logger.warning(f"[FollowUp] LLM draft failed, using template: {e}")
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
