import React from 'react';
import { Mic, MicOff, Phone, PhoneOff } from 'lucide-react';
import { AgentExpression, type AgentExpression as Expression } from './AgentExpression';

interface VoiceCallHudProps { channelName: string; setChannelName: (name: string) => void; isConnected: boolean; isConnecting: boolean; isMuted: boolean; onToggleConnect: () => void; onToggleMute: () => void; localVolume: number; remoteVolume: number; agentStatus: 'idle' | 'listening' | 'thinking' | 'speaking'; sentiment?: string; }
const labelFor = (connected: boolean, waiting: boolean, status: string) => !connected ? (waiting ? 'Connecting' : 'Ready when you are') : ({ idle: 'Present and listening', listening: 'Listening carefully', thinking: 'Considering the conversation', speaking: 'Speaking with the buyer' }[status] || 'Present');

export const VoiceCallHud: React.FC<VoiceCallHudProps> = (props) => {
  const { channelName, setChannelName, isConnected, isConnecting, isMuted, onToggleConnect, onToggleMute, localVolume, agentStatus, sentiment } = props;
  const sentimentExpression: Record<string, Expression> = { positive: 'happy', enthusiastic: 'happy', hesitant: 'happy', skeptical: 'happy', neutral: 'happy' };
  const expression: Expression = !isConnected ? (isConnecting ? 'thinking' : 'happy') : agentStatus === 'idle' ? (sentimentExpression[(sentiment || '').toLowerCase()] || 'happy') : agentStatus;
  const statusLabel = labelFor(isConnected, isConnecting, agentStatus);
  return <section className="reference-voice">
    <div className="reference-copy"><p className="editorial-mono text-[10px] uppercase tracking-[.18em] text-[#696862]">Live voice agent / 01</p><h1 className="editorial-serif mt-3 leading-[.9] text-[#20201e]">A voice with<br/><i>presence.</i></h1><p className="mt-5 max-w-xs text-sm leading-6 text-[#696862]">Lively hears the room, reads the signal, and keeps the next move in view.</p></div>
    <div className="reference-agent"><AgentExpression expression={expression} label={statusLabel} /><div className="reference-controls"><input value={channelName} onChange={e => setChannelName(e.target.value)} disabled={isConnected || isConnecting} aria-label="Room name" className="sr-only" />{isConnected && <div className="flex items-center gap-2"><button onClick={onToggleMute} className={`grid h-10 w-10 place-items-center border transition-colors ${isMuted ? 'border-red-500 bg-red-50 text-red-600' : 'border-[#292927] text-[#292927] hover:bg-[#ecebe6]'}`} aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'} title={isMuted ? 'Microphone is muted' : `Microphone active (Input: ${Math.round(localVolume)}%)`}>{isMuted ? <MicOff size={16}/> : <Mic size={16}/>}</button>{!isMuted && <div className="flex items-center gap-1 h-10 px-2.5 border border-[#292927]/20 bg-white/70 backdrop-blur-sm" title={`Microphone input volume: ${Math.round(localVolume)}%`}><span className="editorial-mono text-[9px] uppercase tracking-wider text-[#696862] mr-1">Mic</span>{[10, 25, 50, 75].map((threshold, idx) => <div key={idx} className={`w-1 rounded-full transition-all duration-75 ${localVolume >= threshold ? 'bg-[#6166cf] h-4 shadow-sm' : 'bg-[#d0cec6] h-1.5'}`}/>)}</div>}</div>}<button onClick={onToggleConnect} disabled={isConnecting} className={`reference-call ${isConnected ? 'is-connected' : ''}`}>{isConnected ? <span className="inline-flex items-center gap-2"><PhoneOff size={14}/> End call</span> : <span className="inline-flex items-center gap-2"><Phone size={14}/>{isConnecting ? 'Connecting' : 'Begin call'}</span>}</button></div></div>
  </section>;
};

