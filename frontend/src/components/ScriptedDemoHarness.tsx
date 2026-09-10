import React, { useState } from 'react';
import { ArrowUpRight, RotateCcw } from 'lucide-react';
import { streamCustomLlmChat } from '../services/api';

interface Props { channelName: string; onTurnComplete?: () => void; onReset?: () => void; }

// PS21's example scenario, extended so every "the solution should demonstrate" item is exercised.
const steps = [
  ['Pricing inquiry', 'Hi, we are evaluating real-time voice AI for our sales team. How much does Lively cost?', 'Retrieval'],
  ['Competitor interruption', 'Wait, we were looking at OpenAI Realtime API and Twilio. Why should we choose you instead?', 'Competitor objection'],
  ['Requirements change', "Actually, our sales team just expanded to 80 users and our budget is $100k ARR. I'm the VP of Product, and we need to respond to inbound leads faster. We want to go live by Q1.", 'Memory + qualification'],
  ['Trust objection', "How do I know it won't make things up when it talks to our customers?", 'Trust objection'],
  ['Enterprise demo', 'Okay, that makes sense. Can we book a 30-minute enterprise demo next Tuesday at 2 PM Eastern for our engineers?', 'Availability + booking'],
  ['Human handoff', 'Before we sign anything our legal team needs custom contract terms. Can I talk to a real person?', 'Escalation with context'],
];

export const ScriptedDemoHarness: React.FC<Props> = ({ channelName, onTurnComplete, onReset }) => {
  const [active, setActive] = useState(0); const [playing, setPlaying] = useState(false); const [response, setResponse] = useState('');
  const play = async (index = active) => { if (playing) return; setActive(index); setResponse(''); setPlaying(true); try { await streamCustomLlmChat(channelName, [{ role: 'user', content: steps[index][1] }], part => setResponse(p => p + part)); if (index < steps.length - 1) setActive(index + 1); onTurnComplete?.(); } catch (e: any) { setResponse(`Unable to run this moment: ${e.message}`); } finally { setPlaying(false); } };
  const reset = () => { setActive(0); setResponse(''); onReset?.(); };
  return <section className="border-t hairline pt-8"><div className="flex items-end justify-between border-b hairline pb-4"><div><p className="editorial-mono text-[10px] uppercase tracking-[.16em] text-[#696862]">Guided demonstration</p><h2 className="editorial-serif mt-2 text-3xl">A conversation, in six moments.</h2><p className="mt-2 text-sm text-[#696862]">Retrieval, objections, memory, qualification, availability, booking and a human handoff with context.</p></div><button onClick={reset} className="inline-flex items-center gap-2 text-xs underline underline-offset-4"><RotateCcw size={13}/> Reset conversation</button></div>
    <div>{steps.map(([title, prompt, note], i) => <button key={title} onClick={() => play(i)} disabled={playing} className={`grid w-full gap-4 border-b hairline py-5 text-left sm:grid-cols-[40px_1fr_auto] ${i === active ? 'text-[#292927] dark:text-[#f1f0ea]' : 'text-[#77756e]'} disabled:opacity-50`}><span className="editorial-serif text-2xl">0{i + 1}</span><span><span className="block text-xs font-semibold uppercase tracking-[.13em]">{title}</span><span className="mt-2 block max-w-2xl text-sm leading-6">“{prompt}”</span></span><span className="editorial-mono self-start text-[10px] uppercase tracking-[.1em] text-[#20201e] dark:text-[#f1f0ea] font-semibold">{note}</span></button>)}</div>
    <button onClick={() => play()} disabled={playing} className="mt-6 inline-flex items-center gap-2 border border-[#292927] dark:border-white/20 px-5 py-3 text-[11px] font-semibold uppercase tracking-[.13em] transition hover:bg-[#292927] hover:text-[#f4f3ef] dark:hover:bg-white dark:hover:text-[#141416] disabled:opacity-50">{playing ? 'Lively is responding' : 'Play this moment'} <ArrowUpRight size={14}/></button>
    {response && <article className="mt-7 border-l-2 border-[#20201e] dark:border-[#f1f0ea] pl-5"><p className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#20201e] dark:text-[#f1f0ea] font-semibold">Lively</p><p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[#292927] dark:text-[#f1f0ea]">{response}</p></article>}
  </section>;
};
