import React, { useState } from 'react';
import { ExternalLink, Calendar, CheckCircle2, ArrowRight, ShieldAlert, Lock, Mail, Video, Database } from 'lucide-react';
import { DealState } from '../types';
import { bookDemoSlot, escalateToHuman } from '../services/api';
import { INVITE_STATUS_LABELS } from './CalendarEventCard';

// Reference geometry for hero layout in Live Sales Cockpit
const VIEW = { width: 1000, height: 680 };
const CIRCLE = { cx: 1250, cy: 340, radius: 390 };
const STAGE_Y = [170, 340, 530];
const INK = 'var(--action-ink)';
const MUTED = 'var(--action-muted)';
const ACCENT = '#20201e';

function pointOnArc(y: number) {
  const dy = y - CIRCLE.cy;
  return { x: CIRCLE.cx - Math.sqrt(Math.max(CIRCLE.radius * CIRCLE.radius - dy * dy, 0)), y };
}

const timeOf = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

type StageStatus = 'active' | 'complete' | 'pending';

export const ActionItemsPanel: React.FC<{ dealState: DealState; hero?: boolean }> = ({ dealState, hero = false }) => {
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const channel = dealState.channel_name;
  const escalation = dealState.escalation || null;
  const demo = dealState.scheduled_demo && dealState.scheduled_demo.status === 'CONFIRMED' ? dealState.scheduled_demo : null;
  const conflict = dealState.slot_conflict || null;
  const openSlots = (conflict?.alternatives?.length ? conflict.alternatives : dealState.available_slots) || [];
  const activity = [...(dealState.crm_activity || [])].reverse();
  const lead = dealState.crm_lead;
  const activeIndex = escalation ? 2 : demo ? 1 : 0;

  const handleBook = async (slot: string) => {
    setBusy(slot);
    setNotice(null);
    try {
      const storedUserEmail = typeof window !== 'undefined' ? localStorage.getItem('lively_user_email') || '' : '';
      const targetEmail = (dealState.contact_email || storedUserEmail || '').trim() || null;
      const res = await bookDemoSlot(channel, slot, targetEmail);
      if (res.status === 'unavailable') setNotice(`${slot} was just taken (${res.data.reason}). Pick another slot.`);
    } catch (err) {
      console.error('Failed to book demo slot:', err);
      setNotice('Could not book that slot.');
    } finally {
      setBusy(null);
    }
  };

  const handleEscalate = async () => {
    setBusy('escalate');
    try {
      await escalateToHuman(channel, 'Rep requested a human handoff from the cockpit.');
    } catch (err) {
      console.error('Failed to escalate:', err);
      setNotice('Could not start the handoff.');
    } finally {
      setBusy(null);
    }
  };

  if (!hero) {
    return (
      <section className="border-t hairline pt-8">
        <div className="border-b hairline pb-4">
          <div className="flex items-center justify-between">
            <p className="editorial-mono text-[10px] uppercase tracking-[.16em] text-[#696862] dark:text-[#9aa0ad]">03 / Automated actions</p>
            <span className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#20201e] dark:text-[#f1f0ea] flex items-center gap-1.5 font-semibold">
              <span className="inline-block h-2 w-2 rounded-full bg-[#20201e] dark:bg-[#f1f0ea] animate-pulse" />
              Connected Pipeline
            </span>
          </div>
          <h2 className="editorial-serif mt-2 text-3xl text-[#20201e] dark:text-[#f1f0ea]">Quiet work, done at the right moment.</h2>
          <p className="mt-2 text-sm text-[#696862] dark:text-[#9aa0ad]">What Lively did during this conversation, and what it can still do.</p>
          {notice && <p className="mt-2 text-xs text-[#ef4444]">{notice}</p>}
        </div>

        <div className="relative pt-6 pb-2">
          <div className="hidden md:flex absolute top-[44%] left-[33.333%] -translate-x-1/2 -translate-y-1/2 z-20 w-8 h-8 rounded-full bg-white dark:bg-[#151926] border hairline items-center justify-center text-[#20201e] dark:text-[#f1f0ea] shadow-xs">
            <ArrowRight size={14} />
          </div>
          <div className="hidden md:flex absolute top-[44%] left-[66.666%] -translate-x-1/2 -translate-y-1/2 z-20 w-8 h-8 rounded-full bg-white dark:bg-[#151926] border hairline items-center justify-center text-[#8c8a82] dark:text-[#697284] shadow-xs">
            <ArrowRight size={14} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
            {/* Box 1: CRM */}
            <div className="rounded-2xl border hairline bg-white dark:bg-[#121520] p-6 shadow-2xs flex flex-col transition-all duration-300 hover:border-black/30 dark:hover:border-white/30">
              <div className="flex items-center justify-between">
                <span className="editorial-serif text-3xl text-[#20201e] dark:text-[#f1f0ea]">01</span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] editorial-mono uppercase tracking-[.12em] bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200/80 dark:border-emerald-800/60 font-semibold">
                  <Database size={11} />
                  <span>{lead.external_system === 'hubspot' ? 'HubSpot synced' : 'CRM synced'}</span>
                </span>
              </div>
              <h3 className="mt-4 text-xs font-bold uppercase tracking-[.14em] text-[#20201e] dark:text-[#f1f0ea]">CRM lead</h3>
              <div className="mt-3 p-3.5 rounded-xl bg-[#f7f6f2] dark:bg-[#181c28] border hairline space-y-1.5">
                <div className="text-sm font-semibold text-[#20201e] dark:text-[#f1f0ea]">{lead.company || dealState.company}</div>
                <div className="editorial-mono text-[10px] text-[#8c8a82]">{lead.lead_id || 'lead pending'} · {lead.status}</div>
                <div className="text-xs text-[#696862] dark:text-[#9aa0ad]">
                  Deal value: <span className="font-medium text-[#20201e] dark:text-[#e8e6e1]">{lead.deal_value || 'Unknown'}</span> · Qualification {dealState.qualification_score}/100
                </div>
                <div className="text-[11px] text-[#8c8a82] dark:text-[#717887]">
                  Contact: {dealState.contact_name}{dealState.contact_email ? ` · ${dealState.contact_email}` : ''}
                </div>
              </div>
              <p className="mt-4 editorial-mono text-[9px] uppercase tracking-[.13em] text-[#77756e]">Activity log</p>
              <ul className="mt-1 max-h-44 overflow-y-auto space-y-1.5 pr-1">
                {activity.length === 0 ? (
                  <li className="text-xs italic text-[#8c8a82]">Nothing logged yet.</li>
                ) : activity.slice(0, 8).map((a, i) => (
                  <li key={i} className="text-[11px] leading-4 text-[#55544e] dark:text-[#a09e97]">
                    <span className="editorial-mono mr-1.5 text-[#8c8a82]">{timeOf(a.timestamp)}</span>{a.summary}
                  </li>
                ))}
              </ul>
            </div>

            {/* Box 2: Demo booking */}
            <div className={`rounded-2xl border bg-white dark:bg-[#121520] p-6 shadow-2xs flex flex-col transition-all duration-300 ${demo ? 'border-[#20201e] dark:border-white/30 ring-1 ring-black/10 dark:ring-white/20' : 'hairline hover:border-black/30 dark:hover:border-white/30'}`}>
              <div className="flex items-center justify-between">
                <span className="editorial-serif text-3xl text-[#20201e] dark:text-[#f1f0ea]">02</span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] editorial-mono uppercase tracking-[.12em] bg-[#f4f3ed] text-[#696862] dark:bg-[#181c28] dark:text-[#9aa0ad] border hairline">
                  {demo ? <><Lock size={11} /><span>Confirmed</span></> : <span>{conflict ? 'Slot unavailable' : dealState.pending_demo_request ? 'Picking a time' : 'Standing by'}</span>}
                </span>
              </div>
              <h3 className="mt-4 text-xs font-bold uppercase tracking-[.14em] text-[#20201e] dark:text-[#f1f0ea] flex items-center gap-1.5">
                <span>Demo booking</span>
                {demo && <CheckCircle2 size={13} className="text-emerald-500" />}
              </h3>

              {demo ? (
                <div className="mt-3 p-3.5 rounded-xl bg-[#f7f6f2] dark:bg-[#181c28] border border-[#20201e]/20 dark:border-white/10 space-y-2">
                  <div className="flex items-start gap-2.5">
                    <Calendar size={16} className="text-[#20201e] dark:text-[#f1f0ea] shrink-0 mt-0.5" />
                    <span className="text-sm font-bold text-[#20201e] dark:text-[#f1f0ea] leading-tight">{demo.time}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-[#55544e] dark:text-[#a09e97]">
                    <Mail size={13} className="text-[#20201e] dark:text-[#e8e6e1] shrink-0" />
                    <span className="truncate font-medium">{demo.email || 'Email needed for the invite'}</span>
                  </div>
                  <p className="text-[10px] editorial-mono uppercase text-emerald-600 dark:text-emerald-400">{INVITE_STATUS_LABELS[demo.invite_status || ''] || ''}</p>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <a href={demo.meeting_link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#141416] hover:bg-[#222227] text-white dark:bg-[#18191e] dark:hover:bg-[#252730] dark:text-[#f4f3ef] border border-black/20 dark:border-white/15 text-[11px] font-semibold uppercase tracking-[.08em] transition shadow-xs">
                      <Video size={12} /><span>Video room</span><ExternalLink size={11} />
                    </a>
                    {demo.google_calendar_link && (
                      <a href={demo.google_calendar_link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#181c28] text-[#20201e] dark:text-[#f1f0ea] text-[11px] font-semibold uppercase tracking-[.08em] transition shadow-xs">
                        <Calendar size={12} className="text-[#20201e] dark:text-[#e8e6e1]" /><span>Calendar</span><ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                </div>
              ) : (
                <div className="mt-3 p-3.5 rounded-xl bg-[#f7f6f2] dark:bg-[#181c28] border hairline space-y-2.5">
                  <p className="text-xs leading-relaxed text-[#696862] dark:text-[#9aa0ad]">
                    {conflict ? `${conflict.requested} is unavailable: ${conflict.reason}.` : 'Open slots with a solutions architect:'}
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {openSlots.slice(0, 3).map(slot => (
                      <button
                        key={slot}
                        type="button"
                        onClick={() => handleBook(slot)}
                        disabled={busy !== null}
                        className="inline-flex items-center justify-between gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#121520] text-left text-[11px] font-medium text-[#20201e] dark:text-[#f1f0ea] hover:border-[#20201e] dark:hover:border-white/40 transition disabled:opacity-50"
                      >
                        <span>{slot}</span>
                        <span className="editorial-mono text-[9px] uppercase text-[#20201e] dark:text-[#f1f0ea] font-semibold">{busy === slot ? 'Booking…' : 'Book'}</span>
                      </button>
                    ))}
                    {openSlots.length === 0 && <p className="text-xs italic text-[#8c8a82]">No open slots in the next three weeks.</p>}
                  </div>
                </div>
              )}
            </div>

            {/* Box 3: Human escalation */}
            <div className={`rounded-2xl border bg-white dark:bg-[#121520] p-6 shadow-2xs flex flex-col transition-all duration-300 ${escalation ? 'border-amber-500/80 ring-1 ring-amber-500/20' : 'hairline hover:border-black/30 dark:hover:border-white/30'}`}>
              <div className="flex items-center justify-between">
                <span className="editorial-serif text-3xl text-[#20201e] dark:text-[#f1f0ea]">03</span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] editorial-mono uppercase tracking-[.12em] bg-[#f4f3ed] text-[#696862] dark:bg-[#181c28] dark:text-[#9aa0ad] border hairline">
                  {escalation ? <><ShieldAlert size={11} /><span>Handoff ready</span></> : <span>Standing by</span>}
                </span>
              </div>
              <h3 className="mt-4 text-xs font-bold uppercase tracking-[.14em] text-[#20201e] dark:text-[#f1f0ea]">Human escalation</h3>
              <div className="mt-3 p-3.5 rounded-xl bg-[#f7f6f2] dark:bg-[#181c28] border hairline space-y-2">
                <p className="text-xs leading-relaxed text-[#696862] dark:text-[#9aa0ad]">
                  {escalation
                    ? `${escalation.reason} The brief includes qualification, objections and all ${escalation.transcript_count} turns.`
                    : 'Triggers automatically when the buyer asks for a person, raises contract or legal terms, stays frustrated, or keeps coming back to the same objection.'}
                </p>
                {escalation ? (
                  <a href={escalation.bridge_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-[11px] font-semibold uppercase tracking-[.08em]">
                    Join handoff room <ExternalLink size={11} />
                  </a>
                ) : (
                  <button
                    type="button"
                    onClick={handleEscalate}
                    disabled={busy !== null || dealState.transcript.length === 0}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#121520] text-[11px] font-semibold uppercase tracking-[.08em] text-[#20201e] dark:text-[#f1f0ea] hover:border-amber-500 disabled:opacity-50"
                  >
                    {busy === 'escalate' ? 'Handing off…' : 'Hand off to a human now'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Hero layout for Live Sales Cockpit
  const stages = [
    {
      title: 'CRM auto-synced',
      detail: `${lead.company} · ${lead.deal_value || 'budget unknown'} · qualification ${dealState.qualification_score}/100`,
      status: lead.status,
      trigger: activity[0]?.summary || 'Every change in the conversation is logged to the lead'
    },
    {
      title: 'Demo booked',
      detail: demo
        ? `Reserved ${demo.time}${demo.email ? ` for ${demo.email}` : ' (email needed)'}`
        : conflict ? `${conflict.requested} unavailable; offering ${conflict.alternatives[0] || 'other slots'}` : 'Standing by for a confirmed time.',
      status: demo ? 'Booked' : conflict ? 'Offering alternatives' : 'Standing by',
      trigger: 'Buyer confirms a time the calendar can honour',
      link: demo?.meeting_link,
      calendarLink: demo?.google_calendar_link
    },
    {
      title: 'Human escalation',
      detail: escalation ? escalation.reason : 'A human partner can join when the moment calls for it.',
      status: escalation ? 'Handoff ready' : 'Standing by',
      trigger: escalation ? `${escalation.transcript_count} turns handed over` : 'Buyer asks for a person, legal terms, or repeated frustration',
      link: escalation?.bridge_url
    },
  ];

  return (
    <section className="action-panel-hero">
      <div className="relative mx-auto w-full" style={{ maxWidth: 780 }}>
        <div style={{ paddingTop: `${(VIEW.height / VIEW.width) * 100}%` }} />
        <svg viewBox={`0 0 ${VIEW.width} ${VIEW.height}`} className="absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMid meet" aria-label="Automated action sequence">
          <circle cx={CIRCLE.cx} cy={CIRCLE.cy} r={CIRCLE.radius} fill="none" stroke={INK} strokeWidth="1" opacity=".78" />
          {stages.map((item, index) => {
            const { x, y } = pointOnArc(STAGE_Y[index]);
            const status: StageStatus = index === activeIndex ? 'active' : index < activeIndex ? 'complete' : 'pending';
            return (
              <g key={item.title}>
                <line x1={x - 136} y1={y} x2={x - 13} y2={y} stroke={status === 'pending' ? MUTED : INK} strokeWidth="1" strokeDasharray="5 7" opacity={status === 'active' ? .72 : .45} />
                <circle cx={x} cy={y} r={status === 'active' ? 4.5 : 3} fill={status === 'pending' ? MUTED : INK} style={{ transition: 'fill 300ms, r 300ms' }} />
                <foreignObject x={x - 310} y={y - 50} width={270} height={220} overflow="visible">
                  <div style={{ transition: 'color 300ms' }}>
                    <p className="editorial-serif leading-none" style={{ fontSize: status === 'active' ? 46 : 34, color: status === 'pending' ? MUTED : INK, margin: 0 }}>0{index + 1}</p>
                    <h3 className="mt-2 text-xs uppercase tracking-[.1em]" style={{ color: status === 'pending' ? MUTED : INK, fontWeight: status === 'active' ? 600 : 500, margin: 0 }}>{item.title}</h3>
                    {status === 'active' && (
                      <div className="mt-2 space-y-1">
                        <p className="text-sm" style={{ color: 'var(--action-detail-text)', margin: 0 }}>{item.detail}</p>
                        <p className="editorial-mono flex flex-wrap items-center gap-1.5 text-[11px] uppercase tracking-[.08em]" style={{ color: ACCENT, margin: 0 }}>
                          <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: ACCENT }} />
                          {item.status}
                          {item.link && (
                            <a href={item.link} target="_blank" rel="noreferrer" className="ml-2 inline-flex items-center gap-1 hover:underline" style={{ color: ACCENT }}>
                              Open room <ExternalLink size={11} />
                            </a>
                          )}
                          {item.calendarLink && (
                            <a href={item.calendarLink} target="_blank" rel="noreferrer" className="ml-2 inline-flex items-center gap-1 hover:underline" style={{ color: ACCENT }}>
                              + Calendar <ExternalLink size={11} />
                            </a>
                          )}
                        </p>
                        <p className="text-[11px]" style={{ color: 'var(--action-trigger-text)', margin: 0 }}>Trigger — {item.trigger}</p>
                      </div>
                    )}
                  </div>
                </foreignObject>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
};
