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
  status: 'Active' | 'Addressed' | 'Resolved';
  suggested_rebuttal?: string;
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
  authority: { status: string; role?: string; decision_maker?: boolean };
  need: { status: string; pain_points?: string[]; urgency?: string; scale?: string };
  timeline: { status: string; timeframe?: string; go_live?: string };
}

export interface DealState {
  channel_name: string;
  session_id: string;
  company: string;
  contact_name: string;
  contact_email?: string;
  decision_maker: string;
  needs: string[];
  users: number;
  budget: string;
  timeline: string;
  competitor_mentioned?: string | null;
  objections: ObjectionItem[];
  stage: 'discovery' | 'qualification' | 'objection_handling' | 'demo_scheduling' | 'escalated' | 'closed' | string;
  sentiment: 'Positive' | 'Neutral' | 'Hesitant' | 'Skeptical' | 'Enthusiastic' | string;
  sentiment_score: number;
  buyer_persona: string;
  bant: BANTStatus;
  active_objections: ObjectionItem[];
  resolved_objections: ObjectionItem[];
  action_items: string[];
  scheduled_demo?: {
    meeting_id?: string;
    status: string;
    time: string;
    email: string;
    topic: string;
    meeting_link: string;
    google_calendar_link?: string;
    booked_at: number;
  } | null;
  crm_lead: {
    company: string;
    contact_name: string;
    contact_email?: string;
    deal_value: string;
    status: string;
    notes?: string;
    last_synced?: number;
  };
  next_best_action: string;
  change_log: ChangeLogEntry[];
  transcript: ChatTurn[];
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
  ttft_p50_ms: number;
  ttft_p95_ms: number;
  ttft_mean_ms: number;
  ttft_min_ms: number;
  total_turn_p50_ms: number;
  total_turn_p95_ms: number;
  model_breakdown: Record<string, number>;
}
