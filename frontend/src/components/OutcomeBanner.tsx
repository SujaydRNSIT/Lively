import React from 'react';
import { CheckCircle2, RotateCcw } from 'lucide-react';
import { DealState } from '../types';
import { CalendarEventCard } from './CalendarEventCard';
import { HandoffCard } from './HandoffCard';

interface OutcomeBannerProps {
  dealState: DealState;
  onReset?: () => void;
}

export const OutcomeBanner: React.FC<OutcomeBannerProps> = ({ dealState, onReset }) => {
  const escalation = dealState.escalation || null;
  const demo = dealState.scheduled_demo && dealState.scheduled_demo.status === 'CONFIRMED' ? dealState.scheduled_demo : null;
  const qualified = dealState.lead_qualified;
  const closed = (dealState.stage || '').toLowerCase() === 'closed';

  if (!escalation && !demo && !qualified && !closed) return null;

  const outcomes = [
    escalation && 'Human handoff',
    demo && 'Demo booked',
    qualified && 'Lead qualified',
    closed && 'Won',
  ].filter(Boolean) as string[];

  const bant = dealState.bant;
  const title = escalation
    ? 'A human handoff is ready.'
    : demo
    ? 'A conversation has been reserved.'
    : qualified
    ? 'This lead is qualified.'
    : 'This opportunity is won.';

  const detail = escalation
    ? `${escalation.reason} The account executive has the full conversation (${escalation.transcript_count} turns).`
    : demo
    ? `Confirmed for ${demo.time}${demo.email ? ` with ${demo.email}.` : '. Waiting for the buyer’s email to send the invite.'}`
    : qualified
    ? `Budget ${bant.budget.value}, ${bant.authority.role || 'authority confirmed'}, timeline ${bant.timeline.timeframe}.`
    : `Closed at ${dealState.budget || 'an agreed value'}.`;

  return (
    <aside className="border-y border-[#6166cf] py-5 space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="editorial-mono text-[10px] uppercase tracking-[.15em] text-[#6166cf] flex flex-wrap items-center gap-1.5">
            <CheckCircle2 className="h-3 w-3" />
            <span>{outcomes.length > 1 ? 'Outcomes reached' : 'A meaningful outcome'}</span>
            {outcomes.map(o => (
              <span key={o} className="rounded-full border border-[#6166cf]/30 px-2 py-0.5 normal-case tracking-normal">{o}</span>
            ))}
          </p>
          <h2 className="editorial-serif text-3xl mt-1">{title}</h2>
          <p className="mt-1 text-sm text-[#4c4b46] dark:text-[#9aa0ad]">{detail}</p>
        </div>

        {onReset && (
          <button
            onClick={onReset}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#151926] text-xs font-medium text-[#4c4b46] dark:text-[#d1d5db] hover:bg-[#f3f2eb] dark:hover:bg-[#1e2436] transition cursor-pointer"
          >
            <RotateCcw size={13} className="text-[#6166cf]" />
            <span>Start Fresh Call</span>
          </button>
        )}
      </div>

      {escalation && <HandoffCard escalation={escalation} />}
      {demo && <CalendarEventCard channelName={dealState.channel_name} demoData={demo} />}
    </aside>
  );
};
