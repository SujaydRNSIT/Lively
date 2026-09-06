import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("lively.tools.crm")

class CRMService:
    """
    Task 8.1: CRM Tool Implementation.
    Provides create_lead, update_lead, log_activity with a clean swappable HubSpot/Salesforce sandbox interface.
    """
    def __init__(self):
        self._leads_store: Dict[str, Dict[str, Any]] = {}
        self._activity_log: list[Dict[str, Any]] = []

    async def create_lead(
        self,
        company_name: str,
        contact_name: str = "Prospect",
        email: Optional[str] = None,
        deal_value: str = "$50,000 ARR",
        notes: str = ""
    ) -> Dict[str, Any]:
        lead_id = f"crm_{abs(hash(company_name)) % 100000}"
        lead_data = {
            "lead_id": lead_id,
            "company": company_name,
            "contact_name": contact_name,
            "email": email or f"{contact_name.lower().replace(' ', '.')}@{company_name.lower().replace(' ', '')}.com",
            "deal_value": deal_value,
            "stage": "Discovery",
            "notes": notes,
            "created_at": time.time(),
            "updated_at": time.time()
        }
        self._leads_store[lead_id] = lead_data
        logger.info(f"CRM created lead: {lead_id} for {company_name}")
        return {
            "status": "success",
            "action": "create_lead",
            "lead": lead_data,
            "message": f"Created CRM lead '{company_name}' with value {deal_value}."
        }

    async def update_lead(
        self,
        company_name: str,
        stage: str,
        deal_value: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        lead_id = f"crm_{abs(hash(company_name)) % 100000}"
        existing = self._leads_store.get(lead_id, {
            "lead_id": lead_id,
            "company": company_name,
            "contact_name": "Prospect",
            "stage": "Discovery",
            "deal_value": deal_value or "$50,000 ARR",
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
        return {
            "status": "success",
            "action": "update_lead",
            "lead": existing,
            "message": f"Updated CRM lead '{company_name}' to stage '{stage}'."
        }

    async def log_activity(
        self,
        company_name: str,
        activity_type: str = "Voice AI Call Turn",
        summary: str = ""
    ) -> Dict[str, Any]:
        activity = {
            "company": company_name,
            "type": activity_type,
            "summary": summary,
            "timestamp": time.time()
        }
        self._activity_log.append(activity)
        logger.info(f"CRM logged activity for {company_name}: {activity_type}")
        return {
            "status": "success",
            "action": "log_activity",
            "activity": activity,
            "message": f"Activity logged for {company_name}."
        }

crm_service = CRMService()

# Export tool helper functions
async def create_lead(company_name: str, contact_name: str = "Prospect", email: Optional[str] = None, deal_value: str = "$50,000 ARR", notes: str = "") -> Dict[str, Any]:
    return await crm_service.create_lead(company_name, contact_name, email, deal_value, notes)

async def update_lead(company_name: str, stage: str, deal_value: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
    return await crm_service.update_lead(company_name, stage, deal_value, notes)

async def log_activity(company_name: str, activity_type: str = "Voice AI Call Turn", summary: str = "") -> Dict[str, Any]:
    return await crm_service.log_activity(company_name, activity_type, summary)

async def sync_crm_deal(company: str, stage: str, deal_value: str = "$50,000 ARR", notes: str = "") -> Dict[str, Any]:
    return await crm_service.update_lead(company, stage, deal_value, notes)
