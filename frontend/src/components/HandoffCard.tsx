import React from 'react';
import { ExternalLink, ShieldAlert } from 'lucide-react';
import { EscalationRecord } from '../types';

const TRIGGER_LABELS: Record<string, string> = {
  buyer_request: 'Buyer asked for a person',
  legal_terms: 'Contract or legal terms',
  frustration: 'Repeated frustration',
  persistent_objections: 'Objections kept coming back',
  manual: 'Escalated by the rep',
  tool: 'Escalated by the agent',
};

/** The brief an account executive reads before joining, so the buyer never repeats themselves. */
export const HandoffCard: React.FC<{ escalation: EscalationRecord }> = ({ escalation }) => {
  const s = escalation.summary || {};
  const facts: [string, string][] = [
    ['Company', s.company || 'Unknown'],
    ['Contact', s.contact_email ? `${s.contact_name} · ${s.contact_email}` : s.contact_name || 'Unknown'],
    ['Qualification', `${s.qualification_score ?? 0}/100${s.lead_qualified ? ' · qualified' : ''}`],
    ['Budget', s.budget || 'Unknown'],
    ['Authority', s.authority ? `${s.authority}${s.decision_maker === false ? ' (not final say)' : ''}` : 'Unknown'],
    ['Timeline', s.timeline || 'Unknown'],
    ['Seats', s.seats ? String(s.seats) : 'Unknown'],
    ['Need', (s.need || []).join('; ') || 'Unknown'],
    ['Demo', s.scheduled_demo || 'Not booked'],
  ];

  return (
    <div className="rounded-2xl border border-amber-500/60 bg-amber-50/40 dark:bg-amber-950/10 p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-amber-600" />
          <h3 className="text-xs font-bold uppercase tracking-[.14em] text-[#20201e] dark:text-[#f1f0ea]">Handoff brief for the account executive</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[10px] editorial-mono uppercase tracking-[.12em]">
          <span className="rounded-full border border-amber-500/40 px-2 py-0.5 text-amber-700 dark:text-amber-400">{escalation.urgency}</span>
          <span className="rounded-full border hairline px-2 py-0.5 text-[#55544e] dark:text-[#9aa0ad]">{TRIGGER_LABELS[escalation.trigger] || escalation.trigger}</span>
          <a href={escalation.bridge_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-full bg-amber-600 px-2.5 py-0.5 text-white hover:bg-amber-700">
            Join handoff room <ExternalLink size={10} />
          </a>
        </div>
      </div>

      <p className="text-sm text-[#3c3b37] dark:text-[#d1d5db]">{escalation.reason}</p>

      <dl className="grid grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-3">
        {facts.map(([term, value]) => (
          <div key={term}>
            <dt className="editorial-mono text-[9px] uppercase tracking-[.13em] text-[#77756e]">{term}</dt>
            <dd className="mt-0.5 text-sm text-[#292927] dark:text-[#f1f0ea]">{value}</dd>
          </div>
        ))}
      </dl>

      {(s.open_objections || []).length > 0 && (
        <div>
          <p className="editorial-mono text-[9px] uppercase tracking-[.13em] text-[#77756e]">Open objections</p>
          <ul className="mt-1 space-y-1 text-sm text-[#3c3b37] dark:text-[#d1d5db]">
            {(s.open_objections || []).map((o, i) => <li key={i}><strong className="capitalize">{o.type}:</strong> “{o.utterance}”</li>)}
          </ul>
        </div>
      )}

      <div>
        <p className="editorial-mono text-[9px] uppercase tracking-[.13em] text-[#77756e]">
          Last {Math.min(escalation.recent_turns.length, 6)} of {escalation.transcript_count} turns (full transcript attached)
        </p>
        <div className="mt-1 space-y-1.5">
          {escalation.recent_turns.slice(-6).map((turn, i) => (
            <p key={i} className="text-xs leading-5 text-[#3c3b37] dark:text-[#d1d5db]">
              <span className="editorial-mono mr-2 text-[10px] uppercase text-[#20201e] dark:text-[#f1f0ea] font-semibold">{turn.role === 'buyer' ? 'Buyer' : 'Lively'}</span>
              {turn.content}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
};
