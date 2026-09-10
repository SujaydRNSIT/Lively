import React, { useState } from 'react';
import { CheckCircle2, RotateCcw, Mail, Send, FileText, Loader2 } from 'lucide-react';
import { DealState } from '../types';
import { CalendarEventCard } from './CalendarEventCard';
import { HandoffCard } from './HandoffCard';
import { sendFollowUpEmail } from '../services/api';

interface OutcomeBannerProps {
  dealState: DealState;
  onReset?: () => void;
}

export const OutcomeBanner: React.FC<OutcomeBannerProps> = ({ dealState, onReset }) => {
  const [sendBusy,  setSendBusy]  = useState(false);
  const [sendNotice, setSendNotice] = useState<string | null>(null);
  const [emailDraft, setEmailDraft] = useState('');

  const escalation = dealState.escalation || null;
  const demo = dealState.scheduled_demo && dealState.scheduled_demo.status === 'CONFIRMED' ? dealState.scheduled_demo : null;
  const qualified = dealState.lead_qualified;
  const closed = (dealState.stage || '').toLowerCase() === 'closed';
  const followUp = dealState.follow_up_draft || null;

  // Banner appears for any meaningful outcome OR if a follow-up draft is ready
  if (!escalation && !demo && !qualified && !closed && !followUp) return null;

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

      {/* Feature D: Post-Call Follow-Up Draft */}
      {followUp && !followUp.sent && (
        <div className="rounded-2xl border border-[#6166cf]/30 bg-[#f7f6f2] dark:bg-[#0f1118] p-5 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Mail size={14} className="text-[#6166cf]" />
              <span className="text-[10px] editorial-mono uppercase tracking-[.16em] text-[#696862] dark:text-[#9aa0ad] font-semibold">
                Post-Call Follow-Up Draft
              </span>
              <span className="text-[9px] editorial-mono px-1.5 py-0.5 rounded bg-[#eceae2] dark:bg-[#1a1d2a] text-[#8c8a82]">
                {followUp.source === 'llm' ? 'AI generated' : 'Template'}
              </span>
            </div>
            <FileText size={13} className="text-[#c8c6c0]" />
          </div>

          <div className="rounded-xl border hairline bg-white dark:bg-[#151926] p-4 space-y-2">
            <p className="text-xs font-semibold text-[#20201e] dark:text-[#f1f0ea]">
              Subject: {followUp.subject}
            </p>
            <pre className="text-xs text-[#55544e] dark:text-[#a09e97] whitespace-pre-wrap leading-relaxed font-sans">
              {followUp.body}
            </pre>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <input
              id="followup-email-input"
              type="email"
              placeholder={followUp.to_email || dealState.contact_email || 'recipient@company.com'}
              value={emailDraft || followUp.to_email || ''}
              onChange={e => setEmailDraft(e.target.value)}
              className="flex-1 min-w-[200px] px-3 py-1.5 rounded-lg border hairline text-xs bg-white dark:bg-[#151926] text-[#20201e] dark:text-[#e8e6e1]"
            />
            <button
              id="followup-send-btn"
              onClick={async () => {
                const to = (emailDraft || followUp.to_email || '').trim();
                if (!to) { setSendNotice('Enter a recipient email first.'); return; }
                setSendBusy(true);
                setSendNotice(null);
                try {
                  await sendFollowUpEmail(dealState.channel_name, to);
                  setSendNotice(`Sent to ${to}`);
                } catch (e: any) {
                  setSendNotice(e.message || 'Send failed');
                } finally {
                  setSendBusy(false);
                }
              }}
              disabled={sendBusy}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-[#6166cf] hover:bg-[#5257be] text-white text-[11px] font-semibold uppercase tracking-[.08em] transition disabled:opacity-50"
            >
              {sendBusy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
              {sendBusy ? 'Sending…' : 'Send'}
            </button>
          </div>
          {sendNotice && (
            <p className={`text-[11px] ${sendNotice.startsWith('Sent') ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500'}`}>
              {sendNotice}
            </p>
          )}
        </div>
      )}

      {followUp?.sent && (
        <div className="flex items-center gap-2 text-[11px] text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 size={13} />
          <span>Follow-up sent to {followUp.sent_to}</span>
        </div>
      )}
    </aside>
  );
};
