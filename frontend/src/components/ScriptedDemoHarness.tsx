import React, { useState } from 'react';
import { ArrowUpRight, RotateCcw } from 'lucide-react';
import { streamCustomLlmChat } from '../services/api';
interface Props { channelName: string; onTurnComplete?: () => void; }
const steps = [
  ['Pricing inquiry', 'Hi, we are evaluating real-time voice AI for our sales team. How much does Lively cost?', 'Pricing and retrieval'],
  ['Competitor interruption', 'Wait, we were looking at OpenAI Realtime API and Twilio. Why should we choose Agora instead?', 'Objection and comparison'],
  ['Memory change', "Actually, our sales team just expanded to 80 users today and our budget is $100k ARR. I'm the VP of Product.", 'Deal-state memory'],
  ['Book a demo', 'That sounds great. Can we book a 30-minute deep-dive demo tomorrow at 2:00 PM EST for our engineers?', 'Calendar action']
];
export const ScriptedDemoHarness: React.FC<Props> = ({ channelName, onTurnComplete }) => {
  const [active, setActive] = useState(0); const [playing, setPlaying] = useState(false); const [response, setResponse] = useState('');
  const play = async (index = active) => { if (playing) return; setActive(index); setResponse(''); setPlaying(true); try { await streamCustomLlmChat(channelName, [{ role: 'user', content: steps[index][1] }], part => setResponse(p => p + part)); if (index < steps.length - 1) setActive(index + 1); onTurnComplete?.(); } catch (e: any) { setResponse(`Unable to run this moment: ${e.message}`); } finally { setPlaying(false); } };
  return <section className="border-t hairline pt-8"><div className="flex items-end justify-between border-b hairline pb-4"><div><p className="editorial-mono text-[10px] uppercase tracking-[.16em] text-[#696862]">Guided demonstration</p><h2 className="editorial-serif mt-2 text-3xl">A conversation, in four moments.</h2><p className="mt-2 text-sm text-[#696862]">Walk through memory, retrieval, judgment, and action.</p></div><button onClick={() => { setActive(0); setResponse(''); }} className="inline-flex items-center gap-2 text-xs underline underline-offset-4"><RotateCcw size={13}/> Reset</button></div>
    <div>{steps.map(([title, prompt, note], i) => <button key={title} onClick={() => play(i)} disabled={playing} className={`grid w-full gap-4 border-b hairline py-5 text-left sm:grid-cols-[40px_1fr_auto] ${i === active ? 'text-[#292927]' : 'text-[#77756e]'} disabled:opacity-50`}><span className="editorial-serif text-2xl">0{i + 1}</span><span><span className="block text-xs font-semibold uppercase tracking-[.13em]">{title}</span><span className="mt-2 block max-w-2xl text-sm leading-6">“{prompt}”</span></span><span className="editorial-mono self-start text-[10px] uppercase tracking-[.1em] text-[#6166cf]">{note}</span></button>)}</div>
    <button onClick={() => play()} disabled={playing} className="mt-6 inline-flex items-center gap-2 border border-[#292927] px-5 py-3 text-[11px] font-semibold uppercase tracking-[.13em] transition hover:bg-[#292927] hover:text-[#f4f3ef] disabled:opacity-50">{playing ? 'Lively is responding' : 'Play this moment'} <ArrowUpRight size={14}/></button>
    {response && <article className="mt-7 border-l-2 border-[#6166cf] pl-5"><p className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#6166cf]">Lively</p><p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[#292927]">{response}</p></article>}
  </section>;
};
