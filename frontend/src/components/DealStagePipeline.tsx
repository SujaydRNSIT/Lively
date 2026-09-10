import React from 'react';
import { DealState } from '../types';

const stages = [['discovery', 'Discovery'], ['qualification', 'Qualification'], ['objection_handling', 'Objections'], ['demo_scheduling', 'Demo'], ['escalated', 'Handoff'], ['closed', 'Closed']];

export const DealStagePipeline: React.FC<{ dealState: DealState }> = ({ dealState }) => {
  const active = Math.max(0, stages.findIndex(([id]) => id === (dealState.stage || '').toLowerCase()));
  const { bant } = dealState;
  const authority = bant.authority.role
    ? `${bant.authority.role}${bant.authority.decision_maker === true ? ' · decides' : bant.authority.decision_maker === false ? ' · influencer' : ''}`
    : bant.authority.decision_maker === true ? 'Decision maker' : 'Unknown';
  const qualification: [string, string, boolean][] = [
    ['Budget', bant.budget.value || 'Unknown', bant.budget.status === 'Identified'],
    ['Authority', authority, bant.authority.status === 'Identified'],
    ['Need', (bant.need.pain_points || []).join('; ') || 'Unknown', bant.need.status === 'Identified'],
    ['Timeline', bant.timeline.timeframe || 'Unknown', bant.timeline.status === 'Identified'],
  ];
  const facts = [['Seats', dealState.users ? String(dealState.users) : 'Unknown'], ['Competitor', dealState.competitor_mentioned || 'None mentioned'], ['Sentiment', dealState.sentiment || 'Neutral']];

  return <section className="border-y hairline py-7">
    <div className="flex items-end justify-between gap-4">
      <div>
        <p className="editorial-mono text-[10px] uppercase tracking-[.16em] text-[#696862]">Deal signal</p>
        <h2 className="editorial-serif mt-1 text-3xl">The shape of this opportunity</h2>
      </div>
      <div className="text-right">
        <p className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#696862]">Qualification {dealState.qualification_score}/100</p>
        <div className="mt-1.5 h-1.5 w-40 overflow-hidden rounded-full bg-[#e5e3dc] dark:bg-[#1e2436]">
          <div className="h-full bg-[#20201e] dark:bg-[#e8e6e1] transition-all duration-500" style={{ width: `${dealState.qualification_score}%` }} />
        </div>
        {dealState.lead_qualified && <p className="mt-1 editorial-mono text-[10px] uppercase tracking-[.12em] text-emerald-600">Lead qualified</p>}
      </div>
    </div>

    <ol className="mt-8 grid grid-cols-3 gap-y-4 sm:grid-cols-6">{stages.map(([id, name], i) => <li key={id} className="relative border-t pt-3 text-[11px] leading-4 text-[#77756e]"><i className={`absolute -top-[4px] left-0 block h-[7px] w-[7px] rounded-full ${i <= active ? 'bg-[#20201e] dark:bg-[#e8e6e1]' : 'bg-[#cbc9c1] dark:bg-[#383d4d]'}`} /><span className={`editorial-mono block text-[10px] ${i === active ? 'text-[#292927] dark:text-[#f1f0ea]' : 'text-[#918f87]'}`}>0{i + 1}</span><span className={i === active ? 'font-semibold text-[#292927] dark:text-[#f1f0ea]' : ''}>{name}</span></li>)}</ol>

    <dl className="mt-8 grid grid-cols-2 gap-x-5 gap-y-5 border-t hairline pt-5 sm:grid-cols-4">{qualification.map(([term, value, known]) => <div key={term}><dt className="editorial-mono flex items-center gap-1.5 text-[9px] uppercase tracking-[.13em] text-[#77756e]"><span className={`inline-block h-1.5 w-1.5 rounded-full ${known ? 'bg-emerald-500' : 'bg-[#cbc9c1]'}`} />{term}</dt><dd className={`mt-1 text-sm ${known ? 'text-[#292927]' : 'italic text-[#918f87]'}`}>{value}</dd></div>)}</dl>
    <dl className="mt-5 grid grid-cols-3 gap-x-5 border-t hairline pt-5">{facts.map(([term, value]) => <div key={term}><dt className="editorial-mono text-[9px] uppercase tracking-[.13em] text-[#77756e]">{term}</dt><dd className="mt-1 text-sm text-[#292927]">{value}</dd></div>)}</dl>

    <div className="mt-7 border-l-2 border-[#20201e] dark:border-[#e8e6e1] pl-4"><p className="editorial-mono text-[9px] uppercase tracking-[.13em] text-[#20201e] dark:text-[#f1f0ea] font-semibold">Next considered move</p><p className="mt-1 text-sm leading-6 text-[#3c3b37] dark:text-[#d1d5db]">{dealState.next_best_action}</p></div>
  </section>;
};
