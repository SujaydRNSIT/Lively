import time
import uuid
import logging
from typing import Dict, Any, Optional

from app.config import settings
from app.core.background import run_blocking, spawn
from app.db.postgres import async_session_factory, EscalationQueueTable

logger = logging.getLogger("lively.tools.escalation")


class EscalationService:
    """
    Task 8.3: Escalation Tool.
    Builds a warm-handoff record with the qualification snapshot, objections, recent turns and the full
    transcript, queues it (memory + database), and optionally emails the summary to the AE desk.
    """
    def __init__(self):
        self._in_memory_queue: list[Dict[str, Any]] = []

    @staticmethod
    def _summarize(state: Any) -> Dict[str, Any]:
        bant = state.bant
        return {
            "company": state.company,
            "contact_name": state.contact_name,
            "contact_email": state.contact_email,
            "stage": state.stage.value if hasattr(state.stage, "value") else str(state.stage),
            "qualification_score": state.qualification_score,
            "lead_qualified": state.lead_qualified,
            "budget": bant.budget.get("value"),
            "authority": bant.authority.get("role"),
            "decision_maker": bant.authority.get("decision_maker"),
            "need": list(bant.need.get("pain_points") or []),
            "timeline": bant.timeline.get("timeframe"),
            "seats": state.users,
            "competitor": state.competitor_mentioned,
            "sentiment": state.sentiment,
            "open_objections": [{"type": o.type, "utterance": o.utterance} for o in state.objections if not o.resolved],
            "resolved_objections": [o.type for o in state.objections if o.resolved],
            "scheduled_demo": (state.scheduled_demo or {}).get("time"),
        }

    def build_handoff(self, channel_name: str, reason: str, urgency: str = "Immediate",
                      deal_state: Optional[Any] = None, trigger: str = "manual") -> Dict[str, Any]:
        escalation_id = f"esc_{uuid.uuid4().hex[:10]}"
        transcript = [t.model_dump() for t in deal_state.transcript] if deal_state else []
        record = {
            "id": escalation_id,
            "channel_name": channel_name,
            "reason": reason,
            "urgency": urgency,
            "trigger": trigger,
            "status": "QUEUED",
            "created_at": time.time(),
            "bridge_url": f"{settings.MEETING_ROOM_BASE_URL.rstrip('/')}/Lively-Handoff-{escalation_id}",
            "summary": self._summarize(deal_state) if deal_state else {"channel": channel_name},
            "recent_turns": [{"role": t["role"], "content": t["content"]} for t in transcript[-8:]],
            "transcript_count": len(transcript),
            "transcript": transcript,
            "message": f"Warm handoff queued for a human AE with the full conversation ({len(transcript)} turns).",
        }
        self._in_memory_queue.append(record)
        logger.info(f"Escalation {escalation_id} for channel {channel_name}: {reason} ({trigger})")

        spawn(self._persist, record, deal_state.model_dump() if deal_state else {"channel": channel_name})
        if settings.ESCALATION_NOTIFY_EMAIL:
            from app.services.email_service import email_service
            run_blocking(email_service.send_handoff_notification, settings.ESCALATION_NOTIFY_EMAIL, record)
        return record

    async def _persist(self, record: Dict[str, Any], deal_snapshot: Dict[str, Any]) -> None:
        if not async_session_factory:
            return
        try:
            async with async_session_factory() as session:
                session.add(EscalationQueueTable(
                    id=record["id"],
                    channel_name=record["channel_name"],
                    reason=record["reason"],
                    urgency=record["urgency"],
                    deal_state_snapshot=deal_snapshot,
                    transcript_snapshot=record["transcript"],
                    created_at=record["created_at"],
                    status="QUEUED"
                ))
                await session.commit()
        except Exception as e:
            logger.debug(f"Escalation DB persist note: {e}")

    def queue(self) -> list[Dict[str, Any]]:
        return list(self._in_memory_queue)

    async def escalate_to_human(
        self,
        channel_name: str,
        reason: str,
        urgency: str = "Immediate",
        deal_state: Optional[Any] = None
    ) -> Dict[str, Any]:
        if deal_state is None and channel_name:
            from app.core.deal_state_engine import deal_state_engine
            deal_state = deal_state_engine.get_state(channel_name)
        record = self.build_handoff(channel_name, reason, urgency, deal_state)
        return {
            "status": "HOT_TRANSFER_INITIATED",
            "escalation_id": record["id"],
            "channel_name": channel_name,
            "reason": reason,
            "urgency": urgency,
            "bridge_url": record["bridge_url"],
            "message": record["message"],
            "context": record["summary"],
            "transcript_count": record["transcript_count"],
        }

escalation_service = EscalationService()

async def escalate_to_human(channel_name: str, reason: str, urgency: str = "Immediate", deal_state: Optional[Any] = None) -> Dict[str, Any]:
    return await escalation_service.escalate_to_human(channel_name, reason, urgency, deal_state)

async def trigger_human_escalation(reason: str, urgency: str = "Immediate", channel_name: Optional[str] = None, deal_state: Optional[Any] = None) -> Dict[str, Any]:
    return await escalation_service.escalate_to_human(channel_name or "unassigned", reason, urgency, deal_state)
