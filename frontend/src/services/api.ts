import { DealState, AgoraConfig, RAGDocument } from '../types';

export const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/$/, '');
export const API_BASE = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';
const LIVELY_SESSION_KEY = 'lively-session-secret-key-2026';

const getHeaders = () => ({
  'Content-Type': 'application/json',
  'X-Lively-Key': LIVELY_SESSION_KEY
});


export async function fetchAgoraConfig(): Promise<AgoraConfig> {
  try {
    const res = await fetch(`${API_BASE}/agora/config`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch Agora config');
    return await res.json();
  } catch (e) {
    console.warn('Using fallback Agora config:', e);
    return {
      app_id: '',
      has_cert: false,
      agent_uid: 9999,
      default_voice: 'en-US-JennyNeural'
    };
  }
}

export async function generateRtcToken(
  channelName: string,
  uid: number | string = 1001
): Promise<{ token: string; app_id: string }> {
  // Task 3.1: POST /api/rtc-token
  const res = await fetch(`${API_BASE}/rtc-token`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ channel_name: channelName, uid, role: 1 })
  });
  if (!res.ok) throw new Error('Failed to generate RTC token');
  const data = await res.json();
  return { token: data.token, app_id: data.app_id };
}

export async function startConversationalAgent(
  channelName: string,
  customerUid: number | string = 1001
) {
  // Task 3.2: POST /api/agent/start
  const res = await fetch(`${API_BASE}/agent/start`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      channel_name: channelName,
      customer_uid: customerUid
    })
  });
  if (!res.ok) throw new Error('Failed to start Conversational AI agent');
  return await res.json();
}

export async function stopConversationalAgent(agentId: string, channelName?: string) {
  // Task 3.3: POST /api/agent/stop
  const res = await fetch(`${API_BASE}/agent/stop`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ agent_id: agentId, channel_name: channelName })
  });
  if (!res.ok) throw new Error('Failed to stop agent');
  return await res.json();
}

export async function queryAgentStatus(agentId: string) {
  // Task 3.3: GET /api/agent/status/{agent_id}
  const res = await fetch(`${API_BASE}/agent/status/${encodeURIComponent(agentId)}`, {
    headers: getHeaders()
  });
  if (!res.ok) throw new Error('Failed to query agent status');
  return await res.json();
}

export async function fetchDealState(channelName: string): Promise<DealState> {
  const res = await fetch(`${API_BASE}/deal-state/${encodeURIComponent(channelName)}`, {
    headers: getHeaders()
  });
  if (!res.ok) throw new Error('Failed to fetch deal state');
  const json = await res.json();
  return json.data;
}

export async function resolveObjection(channelName: string, objectionId: string): Promise<DealState> {
  const res = await fetch(`${API_BASE}/deal-state/${encodeURIComponent(channelName)}/resolve-objection`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ objection_id: objectionId })
  });
  if (!res.ok) throw new Error('Failed to resolve objection');
  const json = await res.json();
  return json.data;
}

export async function setUserContact(
  channelName: string,
  email: string,
  name?: string,
  company?: string
): Promise<DealState> {
  const res = await fetch(`${API_BASE}/deal-state/${encodeURIComponent(channelName)}/set-contact`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ email, name, company })
  });
  if (!res.ok) throw new Error('Failed to set user contact');
  const json = await res.json();
  return json.data;
}

export async function bookDemoSlot(
  channelName: string,
  timeSlot: string = 'Thursday at 2:00 PM EST',
  email: string = 'alex.rivera@nextgen.ai',
  topic: string = 'Lively Real-Time Voice AI Sales Deep-Dive'
): Promise<any> {
  const res = await fetch(`${API_BASE}/tools/book-demo`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      channel_name: channelName,
      time_slot: timeSlot,
      email,
      topic
    })
  });
  if (!res.ok) throw new Error('Failed to book demo');
  return await res.json();
}

export async function fetchKnowledgeBase(): Promise<RAGDocument[]> {
  try {
    const res = await fetch(`${API_BASE}/knowledge`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch knowledge base');
    const json = await res.json();
    return json.data;
  } catch (e) {
    return [];
  }
}

export async function streamCustomLlmChat(
  channelName: string,
  messages: Array<{ role: string; content: string }>,
  onChunk: (delta: string) => void
): Promise<string> {
  const chatEndpoint = BACKEND_URL ? `${BACKEND_URL}/v1/chat/completions` : '/v1/chat/completions';
  const res = await fetch(`${chatEndpoint}?channel=${encodeURIComponent(channelName)}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Agora-Channel-Name': channelName,
      'X-Lively-Key': LIVELY_SESSION_KEY
    },

    body: JSON.stringify({
      model: 'lively-sales-brain',
      messages,
      stream: true
    })
  });

  if (!res.ok) throw new Error(`Chat error: ${res.statusText}`);
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
      if (line.startsWith('data: ')) {
        const payload = line.replace('data: ', '').trim();
        if (payload === '[DONE]') continue;
        try {
          const parsed = JSON.parse(payload);
          const chunk = parsed.choices?.[0]?.delta?.content || '';
          if (chunk) {
            fullText += chunk;
            onChunk(chunk);
          }
        } catch (e) {
          // ignore incomplete json chunk
        }
      }
    }
  }

  return fullText;
}

export async function sendMeetingInvite(
  channelName: string,
  email: string,
  meetingTime?: string,
  meetingLink?: string
) {
  const res = await fetch(`${API_BASE}/tools/send-meeting-invite`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      channel_name: channelName,
      email,
      meeting_time: meetingTime,
      meeting_link: meetingLink
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to send invite' }));
    throw new Error(err.detail || 'Failed to send invite');
  }
  return await res.json();
}
