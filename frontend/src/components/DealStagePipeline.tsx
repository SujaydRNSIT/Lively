import React from 'react';
import { DealState } from '../types';
const stages = [['discovery','Discovery'], ['qualification','Qualification'], ['objection_handling','Objections'], ['demo_scheduling','Demo'], ['closed','Closed']];
export const DealStagePipeline: React.FC<{ dealState: DealState }> = ({ dealState }) => {
  const active = Math.max(0, stages.findIndex(([id]) => id === dealState.stage.toLowerCase()));
  const facts = [['Deal', dealState.budget || '—'], ['Stage', stages[active][1]], ['Seats', `${dealState.users || '—'}`], ['Timeline', dealState.timeline || '—'], ['Sentiment', dealState.sentiment || 'Neutral']];
  return <section className="border-y hairline py-7"><div className="flex items-end justify-between"><div><p className="editorial-mono text-[10px] uppercase tracking-[.16em] text-[#696862]">Deal signal</p><h2 className="editorial-serif mt-1 text-3xl">The shape of this opportunity</h2></div><p className="hidden editorial-mono text-[10px] text-[#696862] sm:block">{dealState.company}</p></div>
    <ol className="mt-8 grid grid-cols-5">{stages.map(([id, name], i) => <li key={id} className="relative border-t pt-3 text-[11px] leading-4 text-[#77756e]"><i className={`absolute -top-[4px] left-0 block h-[7px] w-[7px] rounded-full ${i <= active ? 'bg-[#6166cf]' : 'bg-[#cbc9c1]'}`} /><span className={`editorial-mono block text-[10px] ${i === active ? 'text-[#292927]' : 'text-[#918f87]'}`}>0{i + 1}</span><span className={i === active ? 'font-semibold text-[#292927]' : ''}>{name}</span></li>)}</ol>
    <dl className="mt-8 grid grid-cols-2 gap-x-5 gap-y-5 border-t hairline pt-5 sm:grid-cols-5">{facts.map(([term, value]) => <div key={term}><dt className="editorial-mono text-[9px] uppercase tracking-[.13em] text-[#77756e]">{term}</dt><dd className="mt-1 text-sm text-[#292927]">{value}</dd></div>)}</dl>
    <div className="mt-7 border-l-2 border-[#6166cf] pl-4"><p className="editorial-mono text-[9px] uppercase tracking-[.13em] text-[#6166cf]">Next considered move</p><p className="mt-1 text-sm leading-6 text-[#3c3b37]">{dealState.next_best_action}</p></div>
  </section>;
};
