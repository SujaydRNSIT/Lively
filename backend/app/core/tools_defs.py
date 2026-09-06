"""
Phase 8: OpenAI-style Tool Definitions and Execution Registry.
"""

import json
import logging
from typing import Dict, Any, List
from app.core.tools_impl.crm import create_lead, update_lead, log_activity
from app.core.tools_impl.calendar import check_availability, book_meeting
from app.core.tools_impl.escalation import escalate_to_human
from app.models.schemas import DealStageEnum

logger = logging.getLogger("lively.tools.registry")

OPENAI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check open demo and technical walkthrough calendar slots with Solutions Architects.",
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
            "description": "Book a confirmed thirty-minute product deep-dive demo with a Senior Solutions Architect.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_slot": {"type": "string", "description": "Confirmed date/time (e.g. 'Tomorrow at 2:00 PM EST')"},
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
            "description": "Create or update CRM account record with pipeline stage, company name, and deal value.",
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
            "description": "Initiate an instantaneous warm transfer to a human Account Executive desk with complete deal context and transcript history.",
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
    logger.info(f"Executing tool call: {tool_name} with args {arguments} on channel {channel_name}")

    if tool_name == "check_availability":
        date_str = arguments.get("date_str", "tomorrow")
        pref = arguments.get("time_preference", "afternoon")
        return await check_availability(date_str, pref)

    elif tool_name == "book_meeting":
        time_slot = arguments.get("time_slot", "Tomorrow at 2:00 PM EST")
        extracted_email = arguments.get("email")
        if not extracted_email or extracted_email in ("prospect@example.com", "alex.rivera@nextgen.ai"):
            email = (deal_state.contact_email if deal_state and getattr(deal_state, "contact_email", None) else None) or \
                    (deal_state.crm_lead.contact_email if deal_state and getattr(deal_state, "crm_lead", None) and getattr(deal_state.crm_lead, "contact_email", None) else None) or \
                    "prospect@example.com"
        else:
            email = extracted_email

        topic = arguments.get("topic", "Agora Real-Time Voice AI Sales Deep-Dive")
        res = await book_meeting(time_slot, email, topic)
        if deal_state:
            deal_state.scheduled_demo = res
            deal_state.stage = DealStageEnum.DEMO_SCHEDULING
            deal_state.action_items.append(f"Demo confirmed for {time_slot} ({email})")
            deal_state.action_items.append(f"Invite dispatched: {email} (Google Meet + Calendar blocked)")
            try:
                from app.services.email_service import email_service
                email_service.send_demo_confirmation(email, res)
            except Exception as e_mail:
                logger.error(f"Failed to auto-dispatch demo email invite: {e_mail}")
        return res

    elif tool_name == "create_or_update_crm_lead":
        company = arguments.get("company_name", "Prospect Company")
        stage_str = arguments.get("stage", "discovery")
        stage_value = DealStageEnum(stage_str) if stage_str in {e.value for e in DealStageEnum} else stage_str
        deal_val = arguments.get("deal_value", "$50,000 ARR")
        notes = arguments.get("notes", "")
        res = await update_lead(company, stage_str, deal_val, notes)
        if deal_state:
            deal_state.company = company
            deal_state.stage = stage_value
            deal_state.budget = deal_val
            deal_state.crm_lead.company = company
            deal_state.crm_lead.status = stage_str
            deal_state.crm_lead.deal_value = deal_val
        return res

    elif tool_name == "escalate_to_human":
        reason = arguments.get("reason", "Enterprise prospect requested live specialist")
        urgency = arguments.get("urgency", "Immediate")
        res = await escalate_to_human(channel_name, reason, urgency, deal_state)
        if deal_state:
            deal_state.stage = DealStageEnum.ESCALATED
            deal_state.action_items.append(f"Escalated: {reason}")
        return res

    return {"status": "error", "message": f"Unknown tool: {tool_name}"}
