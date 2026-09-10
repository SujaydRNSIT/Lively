"""
Agent Decision Trace Builder (Feature A).

Derives a concise, user-facing decision trace from:
  - the buyer understanding dict (already extracted by llm_understanding or rule_based_understanding)
  - the delta of deal-state change-log entries produced during the same turn
  - optional tool calls executed during the turn

The trace has four steps:
  HEARD   — what the system understood from the buyer's words
  DECIDED — which routing / action path was chosen, and why
  DID     — what actions were actually executed (tool calls, stage changes, …)
  RESULT  — the outcome visible to the rep

Nothing here calls an LLM. The cost is O(1) dict operations per turn.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- #
# Intent labels — human-readable version of the intent enum                   #
# --------------------------------------------------------------------------- #
_INTENT_LABELS: Dict[str, str] = {
    "ask_pricing":       "Pricing question",
    "ask_product":       "Product question",
    "compare_competitor":"Competitor comparison",
    "raise_objection":   "Objection raised",
    "request_demo":      "Demo request",
    "request_human":     "Asking for a human rep",
    "provide_info":      "Buyer provided information",
    "small_talk":        "Small talk",
    "other":             "General enquiry",
}

_OBJECTION_LABELS: Dict[str, str] = {
    "pricing":    "pricing concern",
    "competitor": "competitor comparison",
    "latency":    "latency / reliability concern",
    "trust":      "AI trust concern",
    "security":   "security / compliance question",
    "product":    "product fit question",
}

_SENTIMENT_EMOJI: Dict[str, str] = {
    "Positive":     "🟢",
    "Enthusiastic": "🟢",
    "Neutral":      "⚪",
    "Hesitant":     "🟡",
    "Skeptical":    "🟠",
    "Frustrated":   "🔴",
}


# --------------------------------------------------------------------------- #
# Public interface                                                              #
# --------------------------------------------------------------------------- #

def build_reasoning_trace(
    understanding: Dict[str, Any],
    change_log_delta: List[Any],       # ChangeLogEntry objects produced this turn
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    provider_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns a dict:
    {
        "heard":   str,   # what the system understood
        "decided": str,   # routing decision and why
        "did":     list[str],  # actions taken (may be empty)
        "result":  str,   # net outcome visible in the cockpit
        "sentiment": str, # emoji + label
        "provider": str,  # LLM provider used
    }
    """
    heard   = _build_heard(understanding)
    decided = _build_decided(understanding)
    did     = _build_did(change_log_delta, tool_calls or [])
    result  = _build_result(change_log_delta, tool_calls or [], understanding)

    sentiment_label = understanding.get("sentiment", "Neutral")
    sentiment_str   = f"{_SENTIMENT_EMOJI.get(sentiment_label, '⚪')} {sentiment_label}"

    return {
        "heard":     heard,
        "decided":   decided,
        "did":       did,
        "result":    result,
        "sentiment": sentiment_str,
        "provider":  provider_name or "unknown",
    }


# --------------------------------------------------------------------------- #
# Step builders                                                                 #
# --------------------------------------------------------------------------- #

def _build_heard(u: Dict[str, Any]) -> str:
    intent = u.get("intent", "other")
    label  = _INTENT_LABELS.get(intent, "General enquiry")
    parts  = [label]

    objs = u.get("objections") or []
    if objs:
        obj_labels = [_OBJECTION_LABELS.get(o.get("type", ""), o.get("type", "")) for o in objs[:2]]
        parts.append(f"objection: {', '.join(obj_labels)}")

    if u.get("wants_human"):
        parts.append("buyer asked for a human rep")

    if u.get("demo_request"):
        dr_map = {
            "request":          "demo requested",
            "accept_proposed":  "buyer accepted proposed slot",
            "reschedule":       "buyer wants to reschedule",
            "cancel":           "buyer cancelled demo",
            "decline":          "buyer declined demo",
        }
        parts.append(dr_map.get(u["demo_request"], u["demo_request"]))

    if u.get("company"):
        parts.append(f"company: {u['company']}")
    if u.get("budget"):
        parts.append(f"budget: {u['budget']}")
    if u.get("user_count"):
        parts.append(f"seats: {u['user_count']}")

    return " · ".join(parts)


def _build_decided(u: Dict[str, Any]) -> str:
    """Explain which routing path was selected and why."""
    intent = u.get("intent", "other")
    objs   = u.get("objections") or []

    if u.get("wants_human") or u.get("legal_or_contract"):
        return "Route → escalation (buyer asked for a human or raised legal/contract terms)"

    if u.get("demo_request") in ("request", "accept_proposed"):
        return "Route → demo scheduling (buyer signalled intent to book)"

    if objs:
        types = [o.get("type", "") for o in objs]
        if "pricing" in types:
            return "Route → pricing objection handling (rebuttal: explore comparison budget)"
        if "competitor" in types:
            return "Route → competitor comparison rebuttal"
        if "trust" in types or "security" in types:
            return "Route → trust / security rebuttal (refer to documentation + human fallback guarantee)"
        return f"Route → objection handling ({', '.join(set(types))})"

    intent_routes = {
        "ask_pricing":       "Route → pricing answer (state plan costs, check volume)",
        "ask_product":       "Route → product answer (use knowledge base context)",
        "compare_competitor":"Route → competitor differentiation",
        "request_demo":      "Route → demo scheduling",
        "provide_info":      "Route → qualification update + continue discovery",
        "small_talk":        "Route → brief casual reply, pivot back to discovery",
    }
    return intent_routes.get(intent, "Route → general answer (continue discovery)")


def _build_did(change_log_delta: List[Any], tool_calls: List[Dict[str, Any]]) -> List[str]:
    """Enumerate actions taken: state mutations + tool calls."""
    actions: List[str] = []

    # Tool calls (from LLM function-call execution)
    for tc in tool_calls:
        name = tc.get("name", "unknown")
        args = tc.get("arguments", {})
        result = tc.get("result") or {}

        if name == "book_meeting":
            slot = args.get("time_slot", "?")
            status = result.get("status", "")
            if status == "CONFIRMED":
                actions.append(f"Called book_meeting({slot!r}) → CONFIRMED")
            elif status == "UNAVAILABLE":
                actions.append(f"Called book_meeting({slot!r}) → UNAVAILABLE (offered alternatives)")
            else:
                actions.append(f"Called book_meeting({slot!r}) → {status}")

        elif name == "create_or_update_crm_lead":
            company = args.get("company_name", "?")
            stage   = args.get("stage", "?")
            actions.append(f"Called create_or_update_crm_lead(company={company!r}, stage={stage!r})")

        elif name == "escalate_to_human":
            actions.append(f"Called escalate_to_human(reason={args.get('reason', '?')!r})")

        elif name == "check_availability":
            actions.append("Called check_availability → returned open slots")

        elif name == "propose_concession":
            pct = args.get("percentage", "?")
            actions.append(f"Called propose_concession({pct}%) → routed to Deal Desk")

        else:
            actions.append(f"Called {name}({_compact_args(args)})")

    # Deal-state mutations from the change log
    field_messages: Dict[str, str] = {
        "stage":          lambda e: f"Stage advanced → {e.new_value}",
        "company":        lambda e: f"Company identified: {e.new_value}",
        "budget":         lambda e: f"Budget captured: {e.new_value}",
        "users":          lambda e: f"Seat count updated: {e.new_value}",
        "timeline":       lambda e: f"Timeline noted: {e.new_value}",
        "scheduled_demo": lambda e: f"Demo booked: {e.new_value.get('time') if isinstance(e.new_value, dict) else e.new_value}",
        "escalation":     lambda e: "Escalation record created",
        "contact_email":  lambda e: f"Contact email stored: {e.new_value}",
    }
    seen_fields: set = set()
    for entry in change_log_delta:
        field = entry.field
        if field in seen_fields:
            continue
        seen_fields.add(field)
        builder = field_messages.get(field)
        if builder:
            try:
                actions.append(builder(entry))
            except Exception:
                actions.append(f"Updated {field}")

    return actions if actions else ["No tool calls or state changes this turn"]


def _build_result(
    change_log_delta: List[Any],
    tool_calls: List[Dict[str, Any]],
    u: Dict[str, Any],
) -> str:
    """One-line outcome summary — what the rep sees in the cockpit."""
    # Highest priority outcomes first
    for entry in change_log_delta:
        if entry.field == "escalation":
            return "🔶 Escalation started — handoff brief ready for the human rep"
        if entry.field == "scheduled_demo":
            val = entry.new_value
            time_str = val.get("time") if isinstance(val, dict) else str(val)
            return f"📅 Demo confirmed for {time_str}"

    for tc in tool_calls:
        res = tc.get("result") or {}
        if tc.get("name") == "book_meeting":
            if res.get("status") == "CONFIRMED":
                return f"📅 Demo confirmed — {res.get('time', '')}"
            if res.get("status") == "UNAVAILABLE":
                return "⚠️ Requested slot unavailable — alternatives offered"
        if tc.get("name") == "propose_concession":
            return "💼 Concession proposal sent to Deal Desk for authorisation"

    # Qualification advancement
    qual_fields = {"budget", "users", "timeline", "company", "contact_email"}
    updated = {e.field for e in change_log_delta} & qual_fields
    if updated:
        labels = {"budget": "Budget", "users": "Seat count", "timeline": "Timeline", "company": "Company", "contact_email": "Contact email"}
        captured = ", ".join(labels[f] for f in updated if f in labels)
        return f"✅ Qualification updated — {captured} captured"

    # Stage change
    for entry in change_log_delta:
        if entry.field == "stage":
            return f"📊 Deal stage advanced → {entry.new_value}"

    sentiment = u.get("sentiment", "Neutral")
    if sentiment in ("Positive", "Enthusiastic"):
        return "✅ Buyer engaged — no state changes required"
    if sentiment == "Frustrated":
        return "🔴 Buyer frustrated — empathetic response delivered, monitoring"

    return "➡️ Turn handled — discovery continues"


def _compact_args(args: Dict[str, Any]) -> str:
    """Short string representation of tool arguments for display."""
    parts = []
    for k, v in list(args.items())[:3]:
        v_str = repr(v) if isinstance(v, str) else str(v)
        if len(v_str) > 30:
            v_str = v_str[:27] + "…"
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)
