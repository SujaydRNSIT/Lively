import time
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
    id: str = Field(default_factory=lambda: f"obj_{int(time.time()*1000)}")
    type: str = "general" # pricing, competitor, latency, security, complexity
    category: Optional[str] = None
    utterance: str
    resolved: bool = False
    status: str = "Active"
    suggested_rebuttal: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)

ObjectionItem = ObjectionRecord

class Lead(BaseModel):
    company: str = "Prospective Client"
    contact_name: str = "Prospect"
    contact_email: Optional[str] = None
    deal_value: str = "$50,000 ARR"
    status: str = "discovery"
    notes: Optional[str] = ""
    last_synced: Optional[float] = None

class BANTStatus(BaseModel):
    budget: Dict[str, Any] = Field(default_factory=lambda: {"status": "Evaluating", "value": "$50,000 ARR", "notes": ""})
    authority: Dict[str, Any] = Field(default_factory=lambda: {"status": "Identified", "role": "VP Engineering / Product", "decision_maker": True})
    need: Dict[str, Any] = Field(default_factory=lambda: {"status": "Identified", "pain_points": ["Sub-300ms RTC Voice", "Barge-in"], "urgency": "High", "scale": "10 seats"})
    timeline: Dict[str, Any] = Field(default_factory=lambda: {"status": "Evaluating", "timeframe": "Q1 / Immediate", "go_live": ""})

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
    needs: List[str] = Field(default_factory=lambda: ["Low-latency voice", "Barge-in handling"])
    users: int = 10
    budget: str = "$50,000 ARR"
    timeline: str = "Q1"
    competitor_mentioned: Optional[str] = None
    objections: List[ObjectionRecord] = Field(default_factory=list)
    stage: DealStageEnum = DealStageEnum.DISCOVERY
    sentiment: str = "Neutral"
    sentiment_score: float = 0.0
    buyer_persona: str = "Technical / Product Leader"
    bant: BANTStatus = Field(default_factory=BANTStatus)
    active_objections: List[ObjectionRecord] = Field(default_factory=list)
    resolved_objections: List[ObjectionRecord] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    scheduled_demo: Optional[Dict[str, Any]] = None
    crm_lead: Lead = Field(default_factory=Lead)
    next_best_action: str = "Introduce product value proposition and ask about current voice AI stack pain points."
    change_log: List[ChangeLogEntry] = Field(default_factory=list)
    transcript: List[ChatTurn] = Field(default_factory=list)
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
