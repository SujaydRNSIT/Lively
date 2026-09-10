import React, { useState, useEffect, useRef } from 'react';
import { CheckCircle2, RotateCcw, Mail, FileText, Send, Loader2 } from 'lucide-react';
import { DealState } from '../types';
import { CalendarEventCard } from './CalendarEventCard';
import { HandoffCard } from './HandoffCard';
import { sendFollowUpEmail } from '../services/api';

interface OutcomeBannerProps {
  dealState: DealState;
  onReset?: () => void;
}

export const OutcomeBanner: React.FC<OutcomeBannerProps> = ({ dealState, onReset }) => {
  const [manualEmail, setManualEmail] = useState('');
  const [sendBusy,    setSendBusy]    = useState(false);
  const autoSentRef = useRef(false);

  const escalation = dealState.escalation || null;
  const demo = dealState.scheduled_demo && dealState.scheduled_demo.status === 'CONFIRMED' ? dealState.scheduled_demo : null;
  const qualified = dealState.lead_qualified;
  const closed = (dealState.stage || '').toLowerCase() === 'closed';
  const followUp = dealState.follow_up_draft || null;

  // The destination email is either already in followUp.sent_to, followUp.to_email, or dealState.contact_email
  const destinationEmail = (followUp?.sent_to || followUp?.to_email || dealState.contact_email || '').trim();

  // Directly dispatch to the listed email if not already marked as sent
  useEffect(() => {
    if (followUp && !followUp.sent && destinationEmail && !autoSentRef.current) {
      autoSentRef.current = true;
      setSendBusy(true);
      sendFollowUpEmail(dealState.channel_name, destinationEmail)
        .catch(err => {
          console.warn('[OutcomeBanner] Auto-dispatch follow-up failed:', err);
        })
        .finally(() => {
          setSendBusy(false);
        });
    }
  }, [followUp, destinationEmail, dealState.channel_name]);

  const handleManualDispatch = async () => {
    const to = (manualEmail || destinationEmail).trim();
    if (!to) return;
    setSendBusy(true);
    try {
      await sendFollowUpEmail(dealState.channel_name, to);
    } catch (err) {
      console.warn('[OutcomeBanner] Manual dispatch failed:', err);
    } finally {
      setSendBusy(false);
    }
  };

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
    <aside className="border-y border-[#20201e] dark:border-neutral-700 py-5 space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="editorial-mono text-[10px] uppercase tracking-[.15em] text-[#20201e] dark:text-[#f1f0ea] flex flex-wrap items-center gap-1.5">
            <CheckCircle2 className="h-3 w-3" />
            <span>{outcomes.length > 1 ? 'Outcomes reached' : 'A meaningful outcome'}</span>
            {outcomes.map(o => (
              <span key={o} className="rounded-full border border-[#20201e]/30 dark:border-white/20 px-2 py-0.5 normal-case tracking-normal">{o}</span>
            ))}
          </p>
          <h2 className="editorial-serif text-3xl mt-1">{title}</h2>
          <p className="mt-1 text-sm text-[#4c4b46] dark:text-[#9aa0ad]">{detail}</p>
        </div>

        {onReset && (
          <button
            onClick={onReset}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#18191e] text-xs font-medium text-[#4c4b46] dark:text-[#d1d5db] hover:bg-[#f3f2eb] dark:hover:bg-[#20222a] transition cursor-pointer"
          >
            <RotateCcw size={13} className="text-[#20201e] dark:text-[#e8e6e1]" />
            <span>Start Fresh Call</span>
          </button>
        )}
      </div>

      {escalation && <HandoffCard escalation={escalation} />}
      {demo && <CalendarEventCard channelName={dealState.channel_name} demoData={demo} />}

      {/* Feature D: Post-Call Follow-Up */}
      {followUp && (
        <div className="rounded-2xl border border-[#20201e]/20 dark:border-white/10 bg-[#f7f6f2] dark:bg-[#141416] p-5 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Mail size={14} className="text-[#20201e] dark:text-[#e8e6e1]" />
              <span className="text-[10px] editorial-mono uppercase tracking-[.16em] text-[#696862] dark:text-[#9aa0ad] font-semibold">
                Post-Call Follow-Up
              </span>
              <span className="text-[9px] editorial-mono px-1.5 py-0.5 rounded bg-[#eceae2] dark:bg-[#1a1b22] text-[#8c8a82]">
                {followUp.source === 'llm' ? 'AI generated' : 'Template'}
              </span>
            </div>
            <FileText size={13} className="text-[#c8c6c0]" />
          </div>

          <div className="rounded-xl border hairline bg-white dark:bg-[#18191e] p-4 space-y-2">
            <p className="text-xs font-semibold text-[#20201e] dark:text-[#f1f0ea]">
              Subject: {followUp.subject}
            </p>
            <pre className="text-xs text-[#55544e] dark:text-[#a09e97] whitespace-pre-wrap leading-relaxed font-sans">
              {followUp.body}
            </pre>
          </div>

          {/* Follow-up status footer - directly shows dispatched without a send button */}
          {destinationEmail ? (
            <div className="flex items-center justify-between flex-wrap gap-2 pt-2 border-t hairline">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-[#20201e] dark:text-[#f1f0ea]" />
                <span className="text-xs font-semibold text-[#20201e] dark:text-[#f1f0ea]">
                  Follow up mail dispatched
                </span>
                <span className="text-xs text-[#696862] dark:text-[#9aa0ad] editorial-mono">
                  → {destinationEmail}
                </span>
              </div>
              <span className="text-[10px] editorial-mono px-2 py-0.5 rounded bg-[#ebe9e1] dark:bg-[#1a1b22] text-[#696862] dark:text-[#9aa0ad]">
                {sendBusy ? 'Dispatching…' : 'Dispatched'}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 pt-2 border-t hairline">
              <input
                id="followup-email-input"
                type="email"
                placeholder="Enter recipient email to dispatch…"
                value={manualEmail}
                onChange={e => setManualEmail(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') handleManualDispatch();
                }}
                className="flex-1 min-w-[200px] px-3 py-1.5 rounded-lg border hairline text-xs bg-white dark:bg-[#18191e] text-[#20201e] dark:text-[#e8e6e1]"
              />
              <button
                id="followup-dispatch-btn"
                onClick={handleManualDispatch}
                disabled={sendBusy || !manualEmail.trim()}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-[#141416] hover:bg-[#222227] text-white dark:bg-[#18191e] dark:hover:bg-[#252730] dark:text-[#f4f3ef] border border-black/20 dark:border-white/15 text-[11px] font-semibold uppercase tracking-[.08em] transition cursor-pointer disabled:opacity-50"
              >
                {sendBusy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                {sendBusy ? 'Dispatching…' : 'Dispatch'}
              </button>
            </div>
          )}
        </div>
      )}
    </aside>
  );
};
