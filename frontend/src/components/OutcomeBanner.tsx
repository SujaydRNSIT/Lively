import React from 'react';
import { ArrowUpRight, CheckCircle2, AlertOctagon } from 'lucide-react';
import { DealState } from '../types';
import { CalendarEventCard } from './CalendarEventCard';

export const OutcomeBanner: React.FC<{ dealState: DealState }> = ({ dealState }) => {
  const stage = (dealState.stage || '').toLowerCase();
  const booked = stage === 'demo_scheduling' || !!dealState.scheduled_demo;
  const escalated = stage === 'escalated';
  const closed = stage === 'closed';

  if (!booked && !escalated && !closed) return null;

  const title = booked
    ? 'A conversation has been reserved.'
    : escalated
    ? 'A human handoff is ready.'
    : 'This opportunity is won.';

  const detail = booked
    ? (dealState.scheduled_demo
        ? `Confirmed for ${dealState.scheduled_demo.time} with ${dealState.scheduled_demo.email}.`
        : 'The buyer has reserved time for a product walkthrough.')
    : escalated
    ? 'The full conversation context is prepared for the account executive.'
    : `Qualified at ${dealState.budget} for ${dealState.users} seats.`;

  return (
    <aside className="border-y border-[#6166cf] py-5 space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="editorial-mono text-[10px] uppercase tracking-[.15em] text-[#6166cf] flex items-center gap-1.5">
            <CheckCircle2 className="h-3 w-3" />
            <span>A meaningful outcome</span>
          </p>
          <h2 className="editorial-serif text-3xl mt-1">{title}</h2>
          <p className="mt-1 text-sm text-[#4c4b46] dark:text-[#9aa0ad]">{detail}</p>
        </div>

        {escalated && (
          <a
            href="https://meet.google.com/new"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#ef4444] text-white text-xs font-semibold shadow-xs transition-transform active:scale-95"
          >
            <AlertOctagon className="h-3.5 w-3.5" />
            <span>Enter Transfer Desk</span>
            <ArrowUpRight size={14} />
          </a>
        )}
      </div>

      {/* Render Calendar UI when Demo is booked */}
      {booked && (
        <div className="mt-4">
          <CalendarEventCard
            channelName={dealState.channel_name}
            demoData={dealState.scheduled_demo}
          />
        </div>
      )}
    </aside>
  );
};
