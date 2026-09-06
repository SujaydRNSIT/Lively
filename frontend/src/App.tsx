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
import { AgoraVoiceManager } from './services/agoraRtc';
import {
  fetchAgoraConfig,
  generateRtcToken,
  startConversationalAgent,
  stopConversationalAgent,
  fetchDealState,
  resolveObjection,
  setUserContact,
} from './services/api';
import { DealState, AgoraConfig } from './types';

const INITIAL_DEAL_STATE: DealState = {
  channel_name: 'lively-sales-room',
  session_id: 'sess_init',
  company: 'NextGen AI Enterprises',
  contact_name: 'Alex Rivera',
  decision_maker: 'VP of Product',
  needs: ['Sub-300ms RTC Voice', 'Barge-in handling'],
  users: 10,
  budget: '$50,000 ARR',
  timeline: 'Q1 / Immediate',
  competitor_mentioned: null,
  objections: [],
  stage: 'discovery',
  sentiment: 'Neutral',
  sentiment_score: 0.0,
  buyer_persona: 'Technical / Product Leader',
  bant: {
    budget: { status: 'Evaluating', value: '$50,000 ARR', notes: '' },
    authority: { status: 'Identified', role: 'VP of Product', decision_maker: true },
    need: { status: 'Identified', pain_points: ['Sub-300ms RTC Voice', 'Barge-in'], urgency: 'High', scale: '10 seats' },
    timeline: { status: 'Evaluating', timeframe: 'Q1 / Immediate', go_live: '' }
  },
  active_objections: [],
  resolved_objections: [],
  action_items: [],
  scheduled_demo: null,
  crm_lead: {
    company: 'NextGen AI Enterprises',
    contact_name: 'Alex Rivera',
    deal_value: '$50,000 ARR',
    status: 'discovery'
  },
  next_best_action: 'Introduce product value proposition and ask about current voice AI stack pain points.',
  change_log: [],
  transcript: [],
  created_at: Date.now() / 1000,
  updated_at: Date.now() / 1000
};

export const App: React.FC = () => {
  const [channelName, setChannelName] = useState<string>('lively-sales-room');
  const [agoraConfig, setAgoraConfig] = useState<AgoraConfig | null>(null);
  const [dealState, setDealState] = useState<DealState>(INITIAL_DEAL_STATE);
  const [activeTab, setActiveTab] = useState<'cockpit' | 'scenario' | 'analytics'>('cockpit');
  
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
  const [userEmail, setUserEmail] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('lively_user_email') || '';
    }
    return '';
  });
  const [userName, setUserName] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('lively_user_name') || '';
    }
    return '';
  });
  const [isEmailModalOpen, setIsEmailModalOpen] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('lively_user_email');
      const prompted = sessionStorage.getItem('lively_prompted_email');
      return !stored && !prompted;
    }
    return false;
  });
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('lively_theme');
      if (saved === 'dark' || saved === 'light') return saved;
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'light';
  });

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

  // Synchronize captured email with the active backend channel
  useEffect(() => {
    if (userEmail && channelName) {
      setUserContact(channelName, userEmail, userName).catch(() => {});
    }
  }, [channelName, userEmail, userName]);

  const handleSaveContact = async (email: string, name?: string, company?: string) => {
    setUserEmail(email);
    if (name) setUserName(name);
    try {
      const updatedState = await setUserContact(channelName, email, name, company);
      if (updatedState) {
        setDealState(updatedState);
      }
    } catch (err) {
      console.error('Failed to sync contact with backend:', err);
    }
  };

  const handleToggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
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
        } else if (local > 5) {
          setAgentStatus('listening');
        } else {
          setAgentStatus('idle');
        }
      },
      onAgentConnected: () => {
        setAgentStatus('speaking');
      },
      onAgentDisconnected: () => {
        setAgentStatus('idle');
      }
    });

    fetchAgoraConfig().then(setAgoraConfig);

    return () => {
      voiceManagerRef.current?.leaveChannel();
      wsRef.current?.close();
    };
  }, []);

  // Sync WebSocket Telemetry on channel change
  useEffect(() => {
    if (!channelName) return;

    fetchDealState(channelName)
      .then(setDealState)
      .catch(() => {});

    const backendEnv = (import.meta.env.VITE_BACKEND_URL || '').trim();
    let wsUrl = '';
    if (backendEnv) {
      const cleanHost = backendEnv.replace(/^https?:\/\//, '').replace(/\/$/, '');
      const wsProtocol = backendEnv.startsWith('https://') ? 'wss:' : 'ws:';
      wsUrl = `${wsProtocol}//${cleanHost}/api/ws/telemetry/${encodeURIComponent(channelName)}`;
    } else {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = window.location.port === '5173' ? 'localhost:8000' : window.location.host;
      wsUrl = `${wsProtocol}//${wsHost}/api/ws/telemetry/${encodeURIComponent(channelName)}`;
    }

    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS] Connected to', wsUrl);
    };

    ws.onerror = (err) => {
      console.error('[WS] Error:', err);
    };

    ws.onclose = (ev) => {
      console.log('[WS] Closed:', ev.code, ev.reason);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'DEAL_STATE_SNAPSHOT' || msg.type === 'DEAL_STATE_UPDATE') {
          setDealState(msg.data);
        } else if (msg.type === 'AGENT_STATUS') {
          setAgentStatus(msg.data.status);
        } else if (msg.type === 'TRANSCRIPT_TURN') {
          if (msg.data.role === 'agent') {
            setAgentStatus('speaking');
          } else if (msg.data.role === 'buyer') {
            setAgentStatus('listening');
          }
          if (msg.data.deal_state) {
            setDealState(msg.data.deal_state);
          } else {
            setDealState((prev) => ({
              ...prev,
              transcript: [
                ...prev.transcript,
                {
                  role: msg.data.role,
                  content: msg.data.text,
                  timestamp: Date.now() / 1000
                }
              ]
            }));
          }
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    return () => {
      ws.close();
    };
  }, [channelName]);

  // Handle Call Connection
  const handleToggleConnect = async () => {
    if (isConnected) {
      await voiceManagerRef.current?.leaveChannel();
      if (agentSessionId) {
        stopConversationalAgent(agentSessionId, channelName).catch(console.error);
        setAgentSessionId(null);
      }
      setIsConnected(false);
      setAgentStatus('idle');
      return;
    }

    try {
      setIsConnecting(true);
      const userUid = Math.floor(1000 + Math.random() * 9000);
      const { token, app_id } = await generateRtcToken(channelName, userUid);

      // Start agent first — this is what triggers LLM callbacks
      const agentRes = await startConversationalAgent(channelName, userUid);
      if (agentRes.agent_id) {
        setAgentSessionId(agentRes.agent_id);
      }

      // Join voice channel (non-blocking — agent works even if local join fails)
      if (app_id && app_id !== 'demo_app_id') {
        voiceManagerRef.current?.joinChannel(app_id, channelName, token, userUid).catch((e) => {
          console.warn('Voice join failed (agent still active):', e);
        });
      }

      setIsConnected(true);
    } catch (err: any) {
      console.error('Agent start failed:', err);
      setIsConnected(true);
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
      const updated = await resolveObjection(channelName, id);
      setDealState(updated);
    } catch (e) {
      console.error('Failed to resolve objection:', e);
    }
  };

  return (
    <div className="min-h-screen flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Top Navigation */}
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

      {/* Main Dashboard Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Task 9.5: Prominent Outcome Banner */}
        <OutcomeBanner dealState={dealState} />

        {/* Voice Call HUD and live automation orbit - rendered in Live Sales Cockpit and Scripted Demo Harness */}
        {(activeTab === 'cockpit' || activeTab === 'scenario') && (
          <div className={activeTab === 'cockpit' ? 'reference-hero' : 'relative'}>
            <VoiceCallHud
              channelName={channelName}
              setChannelName={setChannelName}
              isConnected={isConnected}
              isConnecting={isConnecting}
              isMuted={isMuted}
              onToggleConnect={handleToggleConnect}
              onToggleMute={handleToggleMute}
              localVolume={localVolume}
              remoteVolume={remoteVolume}
              agentStatus={agentStatus}
            />
            {activeTab === 'cockpit' && <ActionItemsPanel dealState={dealState} hero />}
          </div>
        )}

        {/* Tab 1: Live Sales Cockpit */}
        {activeTab === 'cockpit' && (
          <div className="space-y-6">
            {/* Live Diarized Audio Transcript & Real-Time Objection Battlecards Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-7">
                <LiveTranscriptStream transcript={dealState.transcript.map(t => ({ role: t.role as any, text: t.content, timestamp: t.timestamp }))} />
              </div>
              <div className="lg:col-span-5">
                <ObjectionBattlecards
                  activeObjections={dealState.active_objections}
                  resolvedObjections={dealState.resolved_objections}
                  onResolve={handleResolveObjection}
                />
              </div>
            </div>

            {/* Deal Stage Progression & BANT Scorecard */}
            <DealStagePipeline dealState={dealState} />

            {/* Sandbox Tester */}
            <SandboxTester channelName={channelName} />
          </div>
        )}

        {/* Tab 2: Scripted Demo Scenario Harness */}
        {activeTab === 'scenario' && (
          <div className="space-y-6">
            <ScriptedDemoHarness
              channelName={channelName}
              onTurnComplete={() => fetchDealState(channelName).then(setDealState)}
            />
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-7">
                <LiveTranscriptStream transcript={dealState.transcript.map(t => ({ role: t.role as any, text: t.content, timestamp: t.timestamp }))} />
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

        {/* Tab 3: Analytics & Observability */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <AnalyticsDashboard dealState={dealState} />
            <ActionItemsPanel dealState={dealState} />
          </div>
        )}
      </main>

      {/* RAG Knowledge Base Modal */}
      <KnowledgeBaseModal
        isOpen={isKnowledgeOpen}
        onClose={() => setIsKnowledgeOpen(false)}
      />

      {/* Entry Email Capture & Notification Preferences Modal */}
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
