import time
import uuid
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DealStageEnum(str, Enum):
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    OBJECTION_HANDLING = "objection_handling"
    DEMO_SCHEDULING = "demo_scheduling"
    ESCALATED = "escalated"
    CLOSED = "closed"

class ChatTurn(BaseModel):
    role: str # "buyer", "agent", "system", "tool"
    content: str
    timestamp: float = Field(default_factory=time.time)
    sentiment: Optional[str] = "Neutral"

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    timestamp: float = Field(default_factory=time.time)

class ObjectionRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"obj_{uuid.uuid4().hex[:10]}")
    type: str = "general" # pricing, competitor, latency, trust, security, product
    category: Optional[str] = None
    utterance: str
    resolved: bool = False
    status: str = "Active"
    # How it was resolved: accepted | moved_on | advanced_to_demo | manual
    resolution: Optional[str] = None
    suggested_rebuttal: Optional[str] = None
    times_raised: int = 1
    turns_since_raised: int = 0
    timestamp: float = Field(default_factory=time.time)

ObjectionItem = ObjectionRecord

class Lead(BaseModel):
    lead_id: Optional[str] = None
    company: str = "Prospective Client"
    contact_name: str = "Prospect"
    contact_email: Optional[str] = None
    deal_value: Optional[str] = None
    status: str = "discovery"
    notes: Optional[str] = ""
    last_synced: Optional[float] = None
    external_system: Optional[str] = None
    external_id: Optional[str] = None

class BANTStatus(BaseModel):
    # Every dimension starts Unknown and is only marked Identified from what the buyer actually says.
    budget: Dict[str, Any] = Field(default_factory=lambda: {"status": "Unknown", "value": None, "notes": ""})
    authority: Dict[str, Any] = Field(default_factory=lambda: {"status": "Unknown", "role": None, "decision_maker": None})
    need: Dict[str, Any] = Field(default_factory=lambda: {"status": "Unknown", "pain_points": [], "urgency": None, "scale": None})
    timeline: Dict[str, Any] = Field(default_factory=lambda: {"status": "Unknown", "timeframe": None, "go_live": ""})

class ChangeLogEntry(BaseModel):
    field: str
    old_value: Any
    new_value: Any
    timestamp: float = Field(default_factory=time.time)
    description: str

class DealState(BaseModel):
    channel_name: str
    session_id: str
    company: str = "Prospective Client"
    contact_name: str = "Prospect"
    contact_email: Optional[str] = None
    decision_maker: str = "Unknown"
    needs: List[str] = Field(default_factory=list)
    users: Optional[int] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    competitor_mentioned: Optional[str] = None
    objections: List[ObjectionRecord] = Field(default_factory=list)
    stage: DealStageEnum = DealStageEnum.DISCOVERY
    sentiment: str = "Neutral"
    sentiment_score: float = 0.0
    buyer_persona: str = "Unknown"
    bant: BANTStatus = Field(default_factory=BANTStatus)
    qualification_score: int = 0
    lead_qualified: bool = False
    qualified_at: Optional[float] = None
    active_objections: List[ObjectionRecord] = Field(default_factory=list)
    resolved_objections: List[ObjectionRecord] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    scheduled_demo: Optional[Dict[str, Any]] = None
    # Buyer asked for a demo but gave no usable time yet; the agent should offer open slots.
    pending_demo_request: bool = False
    # Requested time was unavailable: {"requested", "reason", "alternatives"}
    slot_conflict: Optional[Dict[str, Any]] = None
    available_slots: List[str] = Field(default_factory=list)
    escalation: Optional[Dict[str, Any]] = None
    crm_lead: Lead = Field(default_factory=Lead)
    crm_activity: List[Dict[str, Any]] = Field(default_factory=list)
    last_understanding: Optional[Dict[str, Any]] = None
    next_best_action: str = "Find out what the buyer is trying to solve before pitching."
    change_log: List[ChangeLogEntry] = Field(default_factory=list)
    transcript: List[ChatTurn] = Field(default_factory=list)
    # Feature A: agent decision trace — populated after every buyer turn
    agent_reasoning: Optional[Dict[str, Any]] = None
    # Feature B: deal desk — most recent concession record for this channel
    deal_desk: Optional[Dict[str, Any]] = None
    # Feature D: post-call follow-up draft — populated on call end
    follow_up_draft: Optional[Dict[str, Any]] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

# API Schemas
class RtcTokenRequest(BaseModel):
    channel_name: str
    uid: int | str = 1001
    role: int = 1

class RtcTokenResponse(BaseModel):
    status: str
    channel_name: str
    uid: int | str
    token: str
    app_id: str

class OpenAIChatMessage(BaseModel):
    role: str
    content: Optional[Any] = ""
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class OpenAIChatCompletionRequest(BaseModel):
    model: Optional[str] = "lively-sales-brain"
    messages: List[OpenAIChatMessage]
    stream: Optional[bool] = True
    stream_options: Optional[Dict[str, Any]] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 200
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = "auto"
    response_format: Optional[Dict[str, Any]] = None
