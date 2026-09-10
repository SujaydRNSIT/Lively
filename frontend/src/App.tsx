import React, { useState, useEffect, useRef } from 'react';
import { Navbar } from './components/Navbar';
import { VoiceCallHud } from './components/VoiceCallHud';
import { DealStagePipeline } from './components/DealStagePipeline';
import { LiveTranscriptStream } from './components/LiveTranscriptStream';
import { ObjectionBattlecards } from './components/ObjectionBattlecards';
import { ActionItemsPanel } from './components/ActionItemsPanel';
import { SandboxTester } from './components/SandboxTester';
import { OutcomeBanner } from './components/OutcomeBanner';
import { ScriptedDemoHarness } from './components/ScriptedDemoHarness';
import { AnalyticsDashboard } from './components/AnalyticsDashboard';
import { KnowledgeBaseModal } from './components/KnowledgeBaseModal';
import { EmailCaptureModal } from './components/EmailCaptureModal';
import { ReasoningTrace } from './components/ReasoningTrace';
import { DealDeskPanel } from './components/DealDeskPanel';
import { SmartDialerPanel } from './components/SmartDialerPanel';
import { AgoraVoiceManager } from './services/agoraRtc';
import {
  ensureSession,
  onSessionChange,
  telemetrySocketUrl,
  fetchAgoraConfig,
  generateRtcToken,
  startConversationalAgent,
  stopConversationalAgent,
  fetchDealState,
  resolveObjection,
  setUserContact,
  resetDealState,
  triggerCallEnd,
} from './services/api';
import { DealState, AgoraConfig } from './types';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

// Everything starts unknown: qualification is only filled in from what the buyer actually says.
const INITIAL_DEAL_STATE: DealState = {
  channel_name: '',
  session_id: 'sess_init',
  company: 'Prospective Client',
  contact_name: 'Prospect',
  contact_email: null,
  decision_maker: 'Unknown',
  needs: [],
  users: null,
  budget: null,
  timeline: null,
  competitor_mentioned: null,
  objections: [],
  stage: 'discovery',
  sentiment: 'Neutral',
  sentiment_score: 0.0,
  buyer_persona: 'Unknown',
  bant: {
    budget: { status: 'Unknown', value: null },
    authority: { status: 'Unknown', role: null, decision_maker: null },
    need: { status: 'Unknown', pain_points: [] },
    timeline: { status: 'Unknown', timeframe: null }
  },
  qualification_score: 0,
  lead_qualified: false,
  active_objections: [],
  resolved_objections: [],
  action_items: [],
  scheduled_demo: null,
  pending_demo_request: false,
  slot_conflict: null,
  available_slots: [],
  escalation: null,
  crm_lead: {
    company: 'Prospective Client',
    contact_name: 'Prospect',
    deal_value: null,
    status: 'discovery'
  },
  crm_activity: [],
  next_best_action: 'Find out what the buyer is trying to solve before pitching.',
  change_log: [],
  transcript: [],
  created_at: Date.now() / 1000,
  updated_at: Date.now() / 1000
};

const readStored = (key: string) => {
  try {
    return typeof window !== 'undefined' ? localStorage.getItem(key) || '' : '';
  } catch {
    return '';
  }
};

export const App: React.FC = () => {
  const [channelName, setChannelName] = useState<string>('');
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [agoraConfig, setAgoraConfig] = useState<AgoraConfig | null>(null);
  const [dealState, setDealState] = useState<DealState>(INITIAL_DEAL_STATE);
  const [activeTab, setActiveTab] = useState<'cockpit' | 'scenario' | 'analytics' | 'dialer'>('cockpit');

  // Feature A: agent decision trace
  const [agentReasoning, setAgentReasoning] = useState<any | null>(null);
  // Feature B: deal desk concession
  const [latestConcession, setLatestConcession] = useState<any | null>(null);

  // Voice call states
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isConnecting, setIsConnecting] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [localVolume, setLocalVolume] = useState<number>(0);
  const [remoteVolume, setRemoteVolume] = useState<number>(0);
  const [agentStatus, setAgentStatus] = useState<'idle' | 'listening' | 'thinking' | 'speaking'>('idle');
  const [agentSessionId, setAgentSessionId] = useState<string | null>(null);

  // UI state
  const [isKnowledgeOpen, setIsKnowledgeOpen] = useState<boolean>(false);
  const [userEmail, setUserEmail] = useState<string>(() => readStored('lively_user_email'));
  const [userName, setUserName] = useState<string>(() => readStored('lively_user_name'));
  const [isEmailModalOpen, setIsEmailModalOpen] = useState<boolean>(() => {
    try {
      return !readStored('lively_user_email') && !sessionStorage.getItem('lively_prompted_email');
    } catch {
      return false;
    }
  });
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = readStored('lively_theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  // Private per-visitor channel
  useEffect(() => {
    const unsubscribe = onSessionChange(session => {
      setChannelName(session.channel_name);
      setDealState({ ...INITIAL_DEAL_STATE, channel_name: session.channel_name });
    });
    ensureSession()
      .then(session => setChannelName(session.channel_name))
      .catch(() => setSessionError('Could not reach the Lively backend. Check that it is running and refresh.'));
    return () => { unsubscribe(); };
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    try {
      localStorage.setItem('lively_theme', theme);
    } catch {
      // ignore storage error
    }
  }, [theme]);

  // Share the visitor's email with their own channel (used for the demo invite)
  useEffect(() => {
    if (channelName && EMAIL_PATTERN.test(userEmail)) {
      setUserContact(channelName, userEmail, userName || undefined).catch(() => {});
    }
  }, [channelName, userEmail, userName]);

  const handleSaveContact = async (email: string, name?: string, company?: string) => {
    setUserEmail(email);
    if (name) setUserName(name);
    if (!channelName) return;
    try {
      const updatedState = await setUserContact(channelName, email, name, company);
      if (updatedState) setDealState(updatedState);
    } catch (err) {
      console.error('Failed to sync contact with backend:', err);
    }
  };

  const handleToggleTheme = () => setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));

  const handleResetSession = async () => {
    try {
      const fresh = await resetDealState(channelName);
      setDealState(fresh || { ...INITIAL_DEAL_STATE, channel_name: channelName });
    } catch (e) {
      console.warn('Reset error, falling back to local initial state:', e);
      setDealState({ ...INITIAL_DEAL_STATE, channel_name: channelName });
    }
  };

  const voiceManagerRef = useRef<AgoraVoiceManager | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Initialize Agora voice manager
  useEffect(() => {
    voiceManagerRef.current = new AgoraVoiceManager({
      onVolumeChange: (local, remote) => {
        setLocalVolume(local);
        setRemoteVolume(remote);
        if (remote > 5) {
          setAgentStatus('speaking');
        } else if (local > 2) {
          setAgentStatus('listening');
        } else {
          setAgentStatus('idle');
        }
      },
      onAgentConnected: () => setAgentStatus('speaking'),
      onAgentDisconnected: () => setAgentStatus('idle')
    });

    fetchAgoraConfig().then(setAgoraConfig);

    return () => {
      voiceManagerRef.current?.leaveChannel();
      wsRef.current?.close();
    };
  }, []);

  // Live updates for this visitor's channel: WebSocket with auto-reconnect, plus a polling fallback
  useEffect(() => {
    if (!channelName) return;

    let isMounted = true;
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const syncDealState = async () => {
      try {
        const state = await fetchDealState(channelName);
        if (isMounted && state) {
          setDealState(prev => ((state.updated_at || 0) >= (prev.updated_at || 0) || prev.channel_name !== state.channel_name ? state : prev));
        }
      } catch {
        // Silently retry on next tick
      }
    };

    syncDealState();
    const pollInterval = setInterval(syncDealState, 2000);

    const connectWebSocket = () => {
      if (!isMounted) return;
      try {
        ws = new WebSocket(telemetrySocketUrl(channelName));
        wsRef.current = ws;
        ws.onerror = (err) => console.warn('[WS] Telemetry connection warning:', err);
        ws.onclose = () => {
          if (isMounted) reconnectTimeout = setTimeout(connectWebSocket, 3000);
        };
        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (!isMounted) return;
            if (msg.type === 'DEAL_STATE_SNAPSHOT' || msg.type === 'DEAL_STATE_UPDATE') {
              setDealState(msg.data);
              // Sync deal desk concession from full state update
              if (msg.data.deal_desk) setLatestConcession(msg.data.deal_desk);
              // Sync follow-up draft is part of dealState already
            } else if (msg.type === 'AGENT_STATUS') {
              setAgentStatus(msg.data.status);
            } else if (msg.type === 'TRANSCRIPT_TURN') {
              setAgentStatus(msg.data.role === 'agent' ? 'speaking' : 'listening');
              if (msg.data.deal_state) setDealState(msg.data.deal_state);
            } else if (msg.type === 'AGENT_REASONING') {
              // Feature A: update the decision trace panel
              setAgentReasoning(msg.data);
            } else if (msg.type === 'DEAL_DESK_UPDATE') {
              // Feature B: update the deal desk panel
              setLatestConcession(msg.data);
            }
          } catch (e) {
            console.error('WS parse error:', e);
          }
        };
      } catch (err) {
        console.warn('Failed to initialize WebSocket, polling is active:', err);
      }
    };

    connectWebSocket();

    return () => {
      isMounted = false;
      clearInterval(pollInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, [channelName]);

  const handleToggleConnect = async () => {
    if (isConnected) {
      await voiceManagerRef.current?.leaveChannel();
      if (agentSessionId) {
        stopConversationalAgent(agentSessionId, channelName).catch(console.error);
        setAgentSessionId(null);
      }
      setIsConnected(false);
      setAgentStatus('idle');
      // Feature D: signal call-end to generate follow-up draft
      if (channelName) triggerCallEnd(channelName).catch(() => {});
      return;
    }

    try {
      setIsConnecting(true);
      const micCheck = await AgoraVoiceManager.checkMicrophone();
      if (!micCheck.available) {
        alert(micCheck.error || 'Microphone access is unavailable. Please check browser permissions.');
        setIsConnecting(false);
        return;
      }

      const userUid = Math.floor(1000 + Math.random() * 9000);
      const { token, app_id } = await generateRtcToken(channelName, userUid);

      const agentRes = await startConversationalAgent(channelName, userUid);
      if (agentRes.agent_id) setAgentSessionId(agentRes.agent_id);

      if (app_id && app_id !== 'demo_app_id') {
        try {
          await voiceManagerRef.current?.joinChannel(app_id, channelName, token, userUid);
        } catch (voiceErr: any) {
          console.error('[AgoraRTC] Local microphone join error:', voiceErr);
          alert(`Microphone Connection Issue: ${voiceErr?.message || 'Could not acquire microphone'}. Please check microphone settings.`);
        }
      }
      setIsConnected(true);
    } catch (err: any) {
      console.error('Agent start failed:', err);
      alert('Unable to connect voice: Please make sure your microphone is connected and permissions are allowed in your browser.');
      setIsConnected(false);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleToggleMute = () => {
    if (!voiceManagerRef.current) return;
    const nextMuted = !isMuted;
    voiceManagerRef.current.setMute(nextMuted);
    setIsMuted(nextMuted);
  };

  const handleResolveObjection = async (id: string) => {
    try {
      setDealState(await resolveObjection(channelName, id));
    } catch (e) {
      console.error('Failed to resolve objection:', e);
    }
  };

  const transcript = dealState.transcript.map(t => ({ role: t.role as any, text: t.content, timestamp: t.timestamp }));

  return (
    <div className="min-h-screen flex flex-col selection:bg-neutral-900 selection:text-white dark:selection:bg-neutral-100 dark:selection:text-neutral-900">
      <Navbar
        agoraConfig={agoraConfig}
        isConnected={isConnected}
        onOpenKnowledge={() => setIsKnowledgeOpen(true)}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        userEmail={userEmail}
        onOpenEmailModal={() => setIsEmailModalOpen(true)}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {!channelName ? (
          <p className="editorial-mono py-24 text-center text-xs uppercase tracking-[.14em] text-[#696862]">
            {sessionError || 'Starting your private session…'}
          </p>
        ) : (
          <>
            <OutcomeBanner dealState={dealState} onReset={handleResetSession} />

            {(activeTab === 'cockpit' || activeTab === 'scenario') && (
              <div className={activeTab === 'cockpit' ? 'reference-hero' : 'relative'}>
                <VoiceCallHud
                  channelName={channelName}
                  setChannelName={() => {}}
                  isConnected={isConnected}
                  isConnecting={isConnecting}
                  isMuted={isMuted}
                  onToggleConnect={handleToggleConnect}
                  onToggleMute={handleToggleMute}
                  localVolume={localVolume}
                  remoteVolume={remoteVolume}
                  agentStatus={agentStatus}
                  sentiment={dealState.sentiment}
                />
                {activeTab === 'cockpit' && <ActionItemsPanel dealState={dealState} hero />}
              </div>
            )}

            {activeTab === 'cockpit' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  <div className="lg:col-span-7 space-y-6">
                    <LiveTranscriptStream transcript={transcript} />
                    {/* Feature A: Agent Decision Trace */}
                    <ReasoningTrace reasoning={agentReasoning} />
                  </div>
                  <div className="lg:col-span-5 space-y-6">
                    <ObjectionBattlecards
                      activeObjections={dealState.active_objections}
                      resolvedObjections={dealState.resolved_objections}
                      onResolve={handleResolveObjection}
                    />
                    {/* Feature B: Deal Desk Negotiation Engine */}
                    <DealDeskPanel
                      channelName={channelName}
                      concession={latestConcession}
                      onUpdate={rec => setLatestConcession(rec)}
                    />
                  </div>
                </div>
                <DealStagePipeline dealState={dealState} />
                <SandboxTester channelName={channelName} />
              </div>
            )}

            {activeTab === 'scenario' && (
              <div className="space-y-6">
                <ScriptedDemoHarness
                  channelName={channelName}
                  onTurnComplete={() => fetchDealState(channelName).then(setDealState).catch(() => {})}
                  onReset={handleResetSession}
                />
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  <div className="lg:col-span-7">
                    <LiveTranscriptStream transcript={transcript} />
                  </div>
                  <div className="lg:col-span-5">
                    <ObjectionBattlecards
                      activeObjections={dealState.active_objections}
                      resolvedObjections={dealState.resolved_objections}
                      onResolve={handleResolveObjection}
                    />
                  </div>
                </div>
                <DealStagePipeline dealState={dealState} />
              </div>
            )}

            {activeTab === 'analytics' && (
              <div className="space-y-6">
                <AnalyticsDashboard dealState={dealState} />
                <ActionItemsPanel dealState={dealState} />
              </div>
            )}

            {/* Feature C: SmartDialer tab */}
            {activeTab === 'dialer' && (
              <div className="space-y-6">
                <SmartDialerPanel />
              </div>
            )}
          </>
        )}
      </main>

      <KnowledgeBaseModal isOpen={isKnowledgeOpen} onClose={() => setIsKnowledgeOpen(false)} />

      <EmailCaptureModal
        isOpen={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
        onSave={handleSaveContact}
        initialEmail={userEmail}
        initialName={userName}
        initialCompany={dealState.company !== 'Prospective Client' ? dealState.company : undefined}
      />
    </div>
  );
};
