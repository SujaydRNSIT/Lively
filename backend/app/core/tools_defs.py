"""
Phase 8: OpenAI-style Tool Definitions and Execution Registry.
Every tool routes through the deal-state engine, so a function call, a REST call and a voice turn all
apply the same availability, CRM and escalation rules.
"""

import logging
from typing import Dict, Any
from app.core.tools_impl.crm import update_lead, crm_service
from app.core.tools_impl.calendar import check_availability

logger = logging.getLogger("lively.tools.registry")

OPENAI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "List open demo slots with Solutions Architects (working days, demo hours, not already booked).",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {"type": "string", "description": "e.g. 'tomorrow', 'next Tuesday'"},
                    "time_preference": {"type": "string", "enum": ["morning", "afternoon", "any"]}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_meeting",
            "description": "Book a product demo with a Senior Solutions Architect. Returns UNAVAILABLE with alternatives if the slot is taken or outside demo hours.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_slot": {"type": "string", "description": "Requested date/time (e.g. 'Tomorrow at 2:00 PM EST')"},
                    "email": {"type": "string", "description": "Prospect contact email address"},
                    "topic": {"type": "string", "description": "Focus topic"}
                },
                "required": ["time_slot"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_or_update_crm_lead",
            "description": "Create or update the CRM lead with company name, pipeline stage and deal value.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "stage": {"type": "string", "enum": ["discovery", "qualification", "objection_handling", "demo_scheduling", "escalated", "closed"]},
                    "deal_value": {"type": "string"},
                    "notes": {"type": "string"}
                },
                "required": ["company_name", "stage"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Hand the conversation to a human Account Executive with the qualification snapshot, objections and full transcript.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Reason for escalation (e.g. custom enterprise legal terms or VIP buyer request)"},
                    "urgency": {"type": "string", "enum": ["Immediate", "High", "Standard"]}
                },
                "required": ["reason"]
            }
        }
    }
]

async def execute_openai_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    channel_name: str,
    deal_state: Any
) -> Dict[str, Any]:
    """
    Task 8.4: Executes OpenAI-style tool calls and binds results back into Deal State.
    """
    from app.core.deal_state_engine import deal_state_engine

    logger.info(f"Executing tool call: {tool_name} with args {arguments} on channel {channel_name}")

    if tool_name == "check_availability":
        return await check_availability(arguments.get("date_str", "tomorrow"), arguments.get("time_preference", "any"))

    if tool_name == "book_meeting":
        return deal_state_engine.book_demo(
            channel_name,
            arguments.get("time_slot") or "",
            email=arguments.get("email"),
            topic=arguments.get("topic"),
        )

    if tool_name == "create_or_update_crm_lead":
        company = arguments.get("company_name", "Prospect Company")
        stage = arguments.get("stage", "discovery")
        deal_value = arguments.get("deal_value")
        res = await update_lead(company, stage, deal_value, arguments.get("notes", ""))
        if deal_state:
            deal_state.company = company
            deal_state.crm_lead.company = company
            if deal_value:
                deal_state.budget = deal_value
                deal_state.crm_lead.deal_value = deal_value
            crm_service.record_activity(deal_state, "crm_update", f"CRM updated: {company} -> {stage}")
            crm_service.upsert_from_state(deal_state)
        return res

    if tool_name == "escalate_to_human":
        return deal_state_engine.escalate(
            channel_name,
            arguments.get("reason", "Enterprise prospect requested a live specialist"),
            arguments.get("urgency", "Immediate"),
            trigger="tool",
        )

    return {"status": "error", "message": f"Unknown tool: {tool_name}"}
