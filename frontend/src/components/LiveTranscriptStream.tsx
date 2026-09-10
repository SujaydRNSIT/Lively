import React, { useEffect, useRef } from 'react';
import { TranscriptTurn } from '../types';
export const LiveTranscriptStream: React.FC<{ transcript: TranscriptTurn[] }> = ({ transcript }) => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (ref.current) ref.current.scrollTo({ top: ref.current.scrollHeight, behavior: 'smooth' }); }, [transcript]);
  return <section className="border-t hairline pt-5"><div className="flex items-baseline justify-between border-b hairline pb-3"><h2 className="editorial-serif text-2xl">The conversation</h2><span className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#696862]">{transcript.length} turns</span></div>
    <div ref={ref} className="mt-1 h-[390px] overflow-y-auto pr-3">
      {transcript.length === 0 ? <div className="grid h-full place-items-center text-center"><div><p className="editorial-serif text-2xl italic text-[#4c4b46]">The room is quiet.</p><p className="mt-2 max-w-xs text-sm leading-6 text-[#77756e]">Begin a call and Lively will place the conversation here as it unfolds.</p></div></div> : transcript.map((turn, i) => <article key={i} className="border-b hairline py-5"><div className="flex items-baseline justify-between"><span className="editorial-mono text-[10px] uppercase tracking-[.16em] text-[#20201e] dark:text-[#f1f0ea] font-semibold">{turn.role === 'buyer' ? 'Buyer' : 'Lively'}</span><time className="editorial-mono text-[10px] text-[#918f87]">{new Date(turn.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></div><p className="mt-2 max-w-xl text-[15px] leading-7 text-[#34332f]">{turn.text || (turn as any).content || ''}</p></article>)}</div>
  </section>;
};
