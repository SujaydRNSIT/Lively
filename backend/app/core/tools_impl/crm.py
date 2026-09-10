import hashlib
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import httpx

from app.config import settings
from app.core.background import spawn

logger = logging.getLogger("lively.tools.crm")

_MAX_ACTIVITY = 30
# Activity types worth a note on the HubSpot contact timeline
_NOTE_EVENTS = {"scheduled_demo", "escalation", "qualification", "objection", "slot_conflict"}


def lead_id_for(key: str) -> str:
    """Stable id (Python's hash() changes every process start)."""
    return "lead_" + hashlib.sha1(key.lower().encode()).hexdigest()[:10]


class HubSpotClient:
    """Optional HubSpot sync using a private-app token. Best effort: failures are logged, never raised."""
    BASE_URL = "https://api.hubapi.com"

    def __init__(self, token: str):
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self._contact_ids: Dict[str, str] = {}
        self._http = httpx.AsyncClient(timeout=8.0)

    async def upsert_contact(self, email: str, properties: Dict[str, Any]) -> Optional[str]:
        try:
            contact_id = self._contact_ids.get(email)
            if not contact_id:
                res = await self._http.post(
                    f"{self.BASE_URL}/crm/v3/objects/contacts/search",
                    headers=self._headers,
                    json={"filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
                          "properties": ["email"], "limit": 1},
                )
                res.raise_for_status()
                results = res.json().get("results", [])
                contact_id = results[0]["id"] if results else None
            if contact_id and properties:
                res = await self._http.patch(f"{self.BASE_URL}/crm/v3/objects/contacts/{contact_id}",
                                             headers=self._headers, json={"properties": properties})
                res.raise_for_status()
            elif not contact_id:
                res = await self._http.post(f"{self.BASE_URL}/crm/v3/objects/contacts",
                                            headers=self._headers, json={"properties": {"email": email, **properties}})
                res.raise_for_status()
                contact_id = res.json()["id"]
            self._contact_ids[email] = contact_id
            return contact_id
        except Exception as e:
            logger.warning(f"HubSpot contact sync failed for {email}: {e}")
            return None

    async def add_note(self, contact_id: str, body: str) -> None:
        try:
            res = await self._http.post(
                f"{self.BASE_URL}/crm/v3/objects/notes",
                headers=self._headers,
                json={
                    "properties": {"hs_timestamp": datetime.now(timezone.utc).isoformat(), "hs_note_body": body},
                    "associations": [{"to": {"id": contact_id},
                                      "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}],
                },
            )
            res.raise_for_status()
        except Exception as e:
            logger.warning(f"HubSpot note failed: {e}")


class CRMService:
    """
    Task 8.1: CRM Tool Implementation.
    In-memory lead store kept in sync with every deal-state change, plus an optional HubSpot mirror.
    """
    def __init__(self):
        self._leads_store: Dict[str, Dict[str, Any]] = {}
        self._activity_log: List[Dict[str, Any]] = []
        self.hubspot = HubSpotClient(settings.HUBSPOT_ACCESS_TOKEN) if settings.HUBSPOT_ACCESS_TOKEN else None

    # ------------------------------------------------------------ deal-state sync
    def upsert_from_state(self, state: Any) -> Dict[str, Any]:
        lead_id = state.crm_lead.lead_id or lead_id_for(state.session_id)
        bant = state.bant
        demo = state.scheduled_demo or {}
        stage = state.stage.value if hasattr(state.stage, "value") else str(state.stage)
        record = {
            "lead_id": lead_id,
            "channel": state.channel_name,
            "company": state.company,
            "contact_name": state.contact_name,
            "email": state.contact_email,
            "stage": stage,
            "deal_value": state.budget,
            "seats": state.users,
            "timeline": state.timeline,
            "authority": bant.authority.get("role"),
            "decision_maker": bant.authority.get("decision_maker"),
            "pain_points": list(bant.need.get("pain_points") or []),
            "qualification_score": state.qualification_score,
            "lead_qualified": state.lead_qualified,
            "open_objections": [o.type for o in state.active_objections],
            "demo": demo.get("time") if demo.get("status") == "CONFIRMED" else None,
            "escalated": bool(state.escalation),
            "updated_at": time.time(),
        }
        self._leads_store[lead_id] = record

        lead = state.crm_lead
        lead.lead_id = lead_id
        lead.company = state.company
        lead.contact_email = state.contact_email
        lead.deal_value = state.budget
        lead.last_synced = record["updated_at"]
        if state.escalation:
            lead.status = "Escalated"
        elif record["demo"]:
            lead.status = "Demo_Scheduled"
        elif state.lead_qualified:
            lead.status = "Qualified"
        else:
            lead.status = stage

        if self.hubspot and state.contact_email:
            spawn(self._push_contact, state, record)
        return record

    def record_activity(self, state: Any, activity_type: str, summary: str) -> Dict[str, Any]:
        entry = {
            "type": activity_type,
            "summary": summary,
            "timestamp": time.time(),
            "lead_id": state.crm_lead.lead_id or lead_id_for(state.session_id),
        }
        self._activity_log.append({**entry, "company": state.company})
        state.crm_activity.append(entry)
        del state.crm_activity[:-_MAX_ACTIVITY]
        if self.hubspot and state.contact_email and activity_type in _NOTE_EVENTS:
            spawn(self._push_note, state.contact_email, f"[Lively] {summary}")
        return entry

    def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        return self._leads_store.get(lead_id)

    async def _push_contact(self, state: Any, record: Dict[str, Any]) -> None:
        properties = {
            "company": record["company"] if record["company"] != "Prospective Client" else None,
            "jobtitle": record["authority"],
            "firstname": state.contact_name if state.contact_name != "Prospect" else None,
        }
        contact_id = await self.hubspot.upsert_contact(record["email"], {k: v for k, v in properties.items() if v})
        if contact_id:
            state.crm_lead.external_system = "hubspot"
            state.crm_lead.external_id = contact_id

    async def _push_note(self, email: str, body: str) -> None:
        contact_id = await self.hubspot.upsert_contact(email, {})
        if contact_id:
            await self.hubspot.add_note(contact_id, body)

    # ------------------------------------------------------------ tool-style API
    async def create_lead(
        self,
        company_name: str,
        contact_name: str = "Prospect",
        email: Optional[str] = None,
        deal_value: Optional[str] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        lead_id = lead_id_for(company_name)
        lead_data = {
            "lead_id": lead_id,
            "company": company_name,
            "contact_name": contact_name,
            "email": email,
            "deal_value": deal_value,
            "stage": "Discovery",
            "notes": notes,
            "created_at": time.time(),
            "updated_at": time.time()
        }
        self._leads_store[lead_id] = lead_data
        logger.info(f"CRM created lead: {lead_id} for {company_name}")
        return {"status": "success", "action": "create_lead", "lead": lead_data, "message": f"Created CRM lead '{company_name}'."}

    async def update_lead(
        self,
        company_name: str,
        stage: str,
        deal_value: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        lead_id = lead_id_for(company_name)
        existing = self._leads_store.get(lead_id, {
            "lead_id": lead_id,
            "company": company_name,
            "contact_name": "Prospect",
            "stage": "Discovery",
            "deal_value": deal_value,
            "notes": ""
        })
        existing["stage"] = stage
        if deal_value:
            existing["deal_value"] = deal_value
        if notes:
            existing["notes"] = f"{existing.get('notes', '')} | {notes}".strip(" | ")
        existing["updated_at"] = time.time()
        self._leads_store[lead_id] = existing
        logger.info(f"CRM updated lead: {lead_id} ({company_name}) -> Stage: {stage}")
        return {"status": "success", "action": "update_lead", "lead": existing, "message": f"Updated CRM lead '{company_name}' to stage '{stage}'."}

    async def log_activity(
        self,
        company_name: str,
        activity_type: str = "Voice AI Call Turn",
        summary: str = ""
    ) -> Dict[str, Any]:
        activity = {"company": company_name, "type": activity_type, "summary": summary, "timestamp": time.time()}
        self._activity_log.append(activity)
        logger.info(f"CRM logged activity for {company_name}: {activity_type}")
        return {"status": "success", "action": "log_activity", "activity": activity, "message": f"Activity logged for {company_name}."}

crm_service = CRMService()

# Export tool helper functions
async def create_lead(company_name: str, contact_name: str = "Prospect", email: Optional[str] = None, deal_value: Optional[str] = None, notes: str = "") -> Dict[str, Any]:
    return await crm_service.create_lead(company_name, contact_name, email, deal_value, notes)

async def update_lead(company_name: str, stage: str, deal_value: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
    return await crm_service.update_lead(company_name, stage, deal_value, notes)

async def log_activity(company_name: str, activity_type: str = "Voice AI Call Turn", summary: str = "") -> Dict[str, Any]:
    return await crm_service.log_activity(company_name, activity_type, summary)

async def sync_crm_deal(company: str, stage: str, deal_value: Optional[str] = None, notes: str = "") -> Dict[str, Any]:
    return await crm_service.update_lead(company, stage, deal_value, notes)
