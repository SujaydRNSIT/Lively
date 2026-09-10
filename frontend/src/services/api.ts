import { DealState, AgoraConfig, RAGDocument } from '../types';

export const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/$/, '');
export const API_BASE = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';
const SESSION_STORAGE_KEY = 'lively_session';

export interface VisitorSession {
  channel_name: string;
  session_token: string;
  expires_at: number;
}

let currentSession: VisitorSession | null = null;
const sessionListeners = new Set<(session: VisitorSession) => void>();

function readStoredSession(): VisitorSession | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function storeSession(session: VisitorSession) {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  } catch {
    // storage unavailable (private mode): the session still works for this tab
  }
}

/**
 * Each visitor gets their own private channel. A stored token resumes the same conversation after
 * a refresh; the server issues a fresh channel if the token is expired or invalid.
 */
export async function ensureSession(): Promise<VisitorSession> {
  if (currentSession && currentSession.expires_at * 1000 > Date.now() + 60_000) return currentSession;
  const stored = currentSession || readStoredSession();
  const res = await fetch(`${API_BASE}/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_token: stored?.session_token ?? null })
  });
  if (!res.ok) throw new Error('Could not start a session');
  const data = await res.json();
  const changed = data.channel_name !== currentSession?.channel_name;
  currentSession = { channel_name: data.channel_name, session_token: data.session_token, expires_at: data.expires_at };
  storeSession(currentSession);
  if (changed) sessionListeners.forEach(listener => listener(currentSession!));
  return currentSession;
}

export function onSessionChange(listener: (session: VisitorSession) => void): () => void {
  sessionListeners.add(listener);
  return () => sessionListeners.delete(listener);
}

const getHeaders = (): Record<string, string> => ({
  'Content-Type': 'application/json',
  ...(currentSession ? { 'X-Lively-Session': currentSession.session_token } : {})
});

async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(url, { ...init, headers: { ...getHeaders(), ...(init.headers || {}) } });
  if (res.status === 401 && currentSession) {
    // Token expired or the server restarted: get a working session (listeners switch the UI over).
    currentSession = { ...currentSession, expires_at: 0 };
    await ensureSession().catch(() => undefined);
  }
  return res;
}

export function telemetrySocketUrl(channelName: string): string {
  const defaultProdBackend = 'https://lively-8s3x.onrender.com';
  const isLocal = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');
  const backendEnv = (import.meta.env.VITE_BACKEND_URL || (isLocal ? '' : defaultProdBackend)).trim();
  const path = `/api/ws/telemetry/${encodeURIComponent(channelName)}?token=${encodeURIComponent(currentSession?.session_token || '')}`;
  if (backendEnv) {
    const cleanHost = backendEnv.replace(/^https?:\/\//, '').replace(/\/$/, '');
    return `${backendEnv.startsWith('https://') ? 'wss:' : 'ws:'}//${cleanHost}${path}`;
  }
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = window.location.port === '5173' ? 'localhost:8000' : window.location.host;
  return `${wsProtocol}//${wsHost}${path}`;
}

export async function fetchAgoraConfig(): Promise<AgoraConfig> {
  try {
    const res = await apiFetch(`${API_BASE}/agora/config`);
    if (!res.ok) throw new Error('Failed to fetch Agora config');
    return await res.json();
  } catch (e) {
    console.warn('Using fallback Agora config:', e);
    return { app_id: '', has_cert: false, agent_uid: 9999, default_voice: 'en-US-JennyNeural' };
  }
}

export async function generateRtcToken(channelName: string, uid: number | string = 1001): Promise<{ token: string; app_id: string }> {
  const res = await apiFetch(`${API_BASE}/rtc-token`, {
    method: 'POST',
    body: JSON.stringify({ channel_name: channelName, uid, role: 1 })
  });
  if (!res.ok) throw new Error('Failed to generate RTC token');
  const data = await res.json();
  return { token: data.token, app_id: data.app_id };
}

export async function startConversationalAgent(channelName: string, customerUid: number | string = 1001) {
  const res = await apiFetch(`${API_BASE}/agent/start`, {
    method: 'POST',
    body: JSON.stringify({ channel_name: channelName, customer_uid: customerUid })
  });
  if (!res.ok) throw new Error('Failed to start Conversational AI agent');
  return await res.json();
}

export async function stopConversationalAgent(agentId: string, channelName: string) {
  const res = await apiFetch(`${API_BASE}/agent/stop`, {
    method: 'POST',
    body: JSON.stringify({ agent_id: agentId, channel_name: channelName })
  });
  if (!res.ok) throw new Error('Failed to stop agent');
  return await res.json();
}

export async function queryAgentStatus(agentId: string) {
  const res = await apiFetch(`${API_BASE}/agent/status/${encodeURIComponent(agentId)}`);
  if (!res.ok) throw new Error('Failed to query agent status');
  return await res.json();
}

export async function fetchDealState(channelName: string): Promise<DealState> {
  const res = await apiFetch(`${API_BASE}/deal-state/${encodeURIComponent(channelName)}`);
  if (!res.ok) throw new Error('Failed to fetch deal state');
  return (await res.json()).data;
}

export async function resolveObjection(channelName: string, objectionId: string): Promise<DealState> {
  const res = await apiFetch(`${API_BASE}/deal-state/${encodeURIComponent(channelName)}/resolve-objection`, {
    method: 'POST',
    body: JSON.stringify({ objection_id: objectionId })
  });
  if (!res.ok) throw new Error('Failed to resolve objection');
  return (await res.json()).data;
}

export async function resetDealState(channelName: string): Promise<DealState> {
  const res = await apiFetch(`${API_BASE}/deal-state/${encodeURIComponent(channelName)}/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset deal state');
  return (await res.json()).data;
}

export async function setUserContact(channelName: string, email: string, name?: string, company?: string): Promise<DealState> {
  const res = await apiFetch(`${API_BASE}/deal-state/${encodeURIComponent(channelName)}/set-contact`, {
    method: 'POST',
    body: JSON.stringify({ email, name, company })
  });
  if (!res.ok) throw new Error('Failed to set user contact');
  return (await res.json()).data;
}

/** Books a slot with the same availability rules as the voice agent. Unavailable slots come back with alternatives. */
export async function bookDemoSlot(channelName: string, timeSlot: string, email?: string | null): Promise<{ status: string; data: any }> {
  const res = await apiFetch(`${API_BASE}/tools/book-demo`, {
    method: 'POST',
    body: JSON.stringify({ channel_name: channelName, time_slot: timeSlot, email: email || null })
  });
  if (!res.ok && res.status !== 409) throw new Error('Failed to book demo');
  return await res.json();
}

export async function escalateToHuman(channelName: string, reason: string) {
  const res = await apiFetch(`${API_BASE}/tools/escalate`, {
    method: 'POST',
    body: JSON.stringify({ channel_name: channelName, reason, urgency: 'High' })
  });
  if (!res.ok) throw new Error('Failed to hand off to a human');
  return await res.json();
}

export async function sendMeetingInvite(channelName: string, email: string) {
  const res = await apiFetch(`${API_BASE}/tools/send-meeting-invite`, {
    method: 'POST',
    body: JSON.stringify({ channel_name: channelName, email })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to send invite' }));
    throw new Error(err.detail || 'Failed to send invite');
  }
  return await res.json();
}

export async function fetchKnowledgeBase(): Promise<RAGDocument[]> {
  try {
    const res = await apiFetch(`${API_BASE}/knowledge`);
    if (!res.ok) throw new Error('Failed to fetch knowledge base');
    return (await res.json()).data;
  } catch {
    return [];
  }
}

export async function streamCustomLlmChat(
  channelName: string,
  messages: Array<{ role: string; content: string }>,
  onChunk: (delta: string) => void
): Promise<string> {
  const chatEndpoint = BACKEND_URL ? `${BACKEND_URL}/v1/chat/completions` : '/v1/chat/completions';
  const res = await apiFetch(`${chatEndpoint}?channel=${encodeURIComponent(channelName)}`, {
    method: 'POST',
    body: JSON.stringify({ model: 'lively-sales-brain', messages, stream: true })
  });

  if (!res.ok) throw new Error(`Chat error: ${res.statusText || res.status}`);
  if (!res.body) return '';

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let fullText = '';
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const payload = line.replace('data: ', '').trim();
      if (payload === '[DONE]') continue;
      try {
        const chunk = JSON.parse(payload).choices?.[0]?.delta?.content || '';
        if (chunk) {
          fullText += chunk;
          onChunk(chunk);
        }
      } catch {
        // ignore incomplete json chunk
      }
    }
  }
  return fullText;
}
