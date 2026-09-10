import React from 'react';
import { ArrowUpRight, Check } from 'lucide-react';
import { ObjectionItem } from '../types';

interface Props { activeObjections: ObjectionItem[]; resolvedObjections: ObjectionItem[]; onResolve: (id: string) => void; }

const RESOLUTION_LABELS: Record<string, string> = {
  accepted: 'buyer accepted the answer',
  moved_on: 'buyer moved on',
  advanced_to_demo: 'buyer booked a demo',
  manual: 'marked handled',
};

export const ObjectionBattlecards: React.FC<Props> = ({ activeObjections, resolvedObjections, onResolve }) => <section className="border-t hairline pt-5">
  <div className="flex items-baseline justify-between border-b hairline pb-3"><h2 className="editorial-serif text-2xl">What needs care</h2><span className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#696862]">{activeObjections.length} live</span></div>
  <div className="h-[390px] overflow-y-auto">
    {activeObjections.length === 0
      ? <div className="grid h-[70%] place-items-center text-center"><div><p className="editorial-serif text-2xl italic text-[#4c4b46]">No resistance right now.</p><p className="mt-2 max-w-xs text-sm leading-6 text-[#77756e]">Pricing, trust, product, security, latency and competitor concerns appear here the moment the buyer raises them.</p></div></div>
      : activeObjections.map(obj => <article key={obj.id} className="border-b hairline py-5">
        <p className="editorial-mono text-[10px] uppercase tracking-[.15em] text-[#6166cf]">Buyer objection / {obj.category || obj.type}{(obj.times_raised || 1) > 1 && <span className="ml-2 text-[#ef4444]">raised {obj.times_raised}×</span>}</p>
        <p className="editorial-serif mt-2 text-xl leading-7 text-[#292927]">“{obj.utterance}”</p>
        {obj.suggested_rebuttal && <><p className="mt-5 editorial-mono text-[9px] uppercase tracking-[.14em] text-[#77756e]">Suggested response</p><p className="mt-2 text-sm leading-6 text-[#4c4b46]">{obj.suggested_rebuttal}</p></>}
        <button onClick={() => onResolve(obj.id)} className="mt-5 inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[.12em] text-[#292927] hover:text-[#6166cf]">Mark handled <ArrowUpRight size={14}/></button>
      </article>)}
    {resolvedObjections.map(obj => <p key={obj.id} className="flex items-center gap-2 border-b hairline py-3 text-xs text-[#77756e]"><Check size={14} className="text-[#6166cf]"/> <span className="capitalize">{obj.category || obj.type}</span> resolved{obj.resolution ? ` — ${RESOLUTION_LABELS[obj.resolution] || obj.resolution}` : ''}</p>)}
  </div>
</section>;
