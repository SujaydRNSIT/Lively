export interface ChatTurn {
  role: 'buyer' | 'agent' | 'system' | 'tool';
  content: string;
  timestamp: number;
  sentiment?: string;
}

export type TranscriptTurn = {
  role: 'buyer' | 'agent' | 'system' | 'tool';
  text: string;
  timestamp: number;
  sentiment?: string;
};

export interface ObjectionItem {
  id: string;
  type: string;
  category?: string;
  utterance: string;
  resolved: boolean;
  status: 'Active' | 'Addressed' | 'Resolved' | string;
  resolution?: 'accepted' | 'moved_on' | 'advanced_to_demo' | 'manual' | string | null;
  suggested_rebuttal?: string;
  times_raised?: number;
  timestamp: number;
}

export interface ChangeLogEntry {
  field: string;
  old_value: any;
  new_value: any;
  timestamp: number;
  description: string;
}

export interface BANTStatus {
  budget: { status: string; value?: string | null; notes?: string };
  authority: { status: string; role?: string | null; decision_maker?: boolean | null };
  need: { status: string; pain_points?: string[]; urgency?: string | null; scale?: string | null };
  timeline: { status: string; timeframe?: string | null; go_live?: string };
}

export interface ScheduledDemo {
  meeting_id?: string;
  status: string;
  time: string;
  email?: string | null;
  topic?: string;
  host?: string;
  duration?: string;
  meeting_link: string;
  google_calendar_link?: string;
  booked_at?: number;
  invite_status?: 'queued' | 'sending' | 'delivered' | 'preview_only' | 'pending_email' | 'rate_limited' | string;
}

export interface SlotConflict {
  requested: string;
  reason: string;
  alternatives: string[];
}

export interface HandoffSummary {
  company?: string;
  contact_name?: string;
  contact_email?: string | null;
  qualification_score?: number;
  lead_qualified?: boolean;
  budget?: string | null;
  authority?: string | null;
  decision_maker?: boolean | null;
  need?: string[];
  timeline?: string | null;
  seats?: number | null;
  competitor?: string | null;
  sentiment?: string;
  open_objections?: { type: string; utterance: string }[];
  resolved_objections?: string[];
  scheduled_demo?: string | null;
}

export interface EscalationRecord {
  id: string;
  reason: string;
  urgency: string;
  trigger: string;
  status: string;
  bridge_url: string;
  created_at: number;
  transcript_count: number;
  recent_turns: { role: string; content: string }[];
  summary: HandoffSummary;
}

export interface CrmActivity {
  type: string;
  summary: string;
  timestamp: number;
  lead_id: string;
}

export interface DealState {
  channel_name: string;
  session_id: string;
  company: string;
  contact_name: string;
  contact_email?: string | null;
  decision_maker: string;
  needs: string[];
  users: number | null;
  budget: string | null;
  timeline: string | null;
  competitor_mentioned?: string | null;
  objections: ObjectionItem[];
  stage: 'discovery' | 'qualification' | 'objection_handling' | 'demo_scheduling' | 'escalated' | 'closed' | string;
  sentiment: 'Positive' | 'Neutral' | 'Hesitant' | 'Skeptical' | 'Frustrated' | 'Enthusiastic' | string;
  sentiment_score: number;
  buyer_persona: string;
  bant: BANTStatus;
  qualification_score: number;
  lead_qualified: boolean;
  qualified_at?: number | null;
  active_objections: ObjectionItem[];
  resolved_objections: ObjectionItem[];
  action_items: string[];
  scheduled_demo?: ScheduledDemo | null;
  pending_demo_request?: boolean;
  slot_conflict?: SlotConflict | null;
  available_slots?: string[];
  escalation?: EscalationRecord | null;
  crm_lead: {
    lead_id?: string | null;
    company: string;
    contact_name: string;
    contact_email?: string | null;
    deal_value?: string | null;
    status: string;
    notes?: string;
    last_synced?: number | null;
    external_system?: string | null;
    external_id?: string | null;
  };
  crm_activity?: CrmActivity[];
  last_understanding?: { source?: string; intent?: string } | null;
  next_best_action: string;
  change_log: ChangeLogEntry[];
  transcript: ChatTurn[];
  /** Feature A: agent decision trace — updated after every buyer turn */
  agent_reasoning?: {
    heard:     string;
    decided:   string;
    did:       string[];
    result:    string;
    sentiment: string;
    provider:  string;
  } | null;
  /** Feature B: most recent deal desk concession record */
  deal_desk?: {
    id:                        string;
    proposed_pct:              number;
    authorised_pct:            number;
    status:                    'approved' | 'pending_manager' | 'refused' | 'expired';
    reason:                    string;
    trade:                     string | null;
    manager_approval_required: boolean;
    approved_by?:              string | null;
    label:                     string;
    bound_by:                  string;
    channel_name:              string;
    expires_at:                number;
  } | null;
  /** Feature D: post-call follow-up email draft */
  follow_up_draft?: {
    subject:      string;
    body:         string;
    to_email:     string;
    generated_at: number;
    source:       'llm' | 'template';
    sent?:        boolean;
    sent_to?:     string;
    sent_at?:     number;
  } | null;
  created_at: number;
  updated_at: number;
}

export interface AgoraConfig {
  app_id: string;
  has_cert: boolean;
  agent_uid: number;
  default_voice: string;
  asr_provider?: string;
  tts_provider?: string;
}

export interface RAGDocument {
  doc_id: string;
  title: string;
  category: string;
  content: string;
  keywords: string[];
}

export interface LatencyStats {
  total_turns: number;
  measured?: boolean;
  ttft_p50_ms: number | null;
  ttft_p95_ms: number | null;
  ttft_mean_ms: number | null;
  ttft_min_ms: number | null;
  total_turn_p50_ms: number | null;
  total_turn_p95_ms: number | null;
  model_breakdown: Record<string, number>;
  failovers?: number;
  partial_turns?: number;
  understanding?: { mode: string; llm: number; timeout: number; error: number };
}
