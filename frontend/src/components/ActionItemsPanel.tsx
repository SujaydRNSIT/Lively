import React, { useState } from 'react';
import { ExternalLink, Calendar, Clock, CheckCircle2, ArrowRight, UserCheck, ShieldAlert, Sparkles, Lock, Mail, Video } from 'lucide-react';
import { DealState } from '../types';
import { bookDemoSlot } from '../services/api';

// Reference geometry for hero layout in Live Sales Cockpit
const VIEW = { width: 1000, height: 680 };
const CIRCLE = { cx: 1250, cy: 340, radius: 390 };
const STAGE_Y = [170, 340, 530];
const INK = 'var(--action-ink)';
const MUTED = 'var(--action-muted)';
const ACCENT = '#6166cf';

function pointOnArc(y: number) {
  const dy = y - CIRCLE.cy;
  return { x: CIRCLE.cx - Math.sqrt(Math.max(CIRCLE.radius * CIRCLE.radius - dy * dy, 0)), y };
}

type StageStatus = 'active' | 'complete' | 'pending';

export const ActionItemsPanel: React.FC<{ dealState: DealState; hero?: boolean }> = ({ dealState, hero = false }) => {
  const [isBookingManual, setIsBookingManual] = useState(false);
  const stage = (dealState.stage || '').toLowerCase();
  const escalated = stage === 'escalated';
  const demoBooked = Boolean(dealState.scheduled_demo) || stage === 'demo_scheduling';
  const activeIndex = escalated ? 2 : demoBooked ? 1 : 0;

  // Box-by-box connected pipeline layout for Telemetry & Observability
  const isDemoSaved = Boolean(dealState.scheduled_demo);
  const demoTime = dealState.scheduled_demo?.time || (stage === 'demo_scheduling' ? 'Thursday at 2:00 PM EST' : 'Pending confirmation');
  const demoEmail = dealState.scheduled_demo?.email || dealState.contact_email || dealState.crm_lead?.contact_email || (typeof window !== 'undefined' ? localStorage.getItem('lively_user_email') : null) || 'alex.rivera@nextgen.ai';
  const calendarBlockUrl = dealState.scheduled_demo?.google_calendar_link;

  const handleQuickLock = async (slot = 'Thursday at 2:00 PM EST') => {
    setIsBookingManual(true);
    try {
      await bookDemoSlot(dealState.channel_name || 'lively-sales-room', slot, demoEmail);
    } catch (err) {
      console.error('Failed to lock demo slot:', err);
    } finally {
      setIsBookingManual(false);
    }
  };

  if (!hero) {

    return (
      <section className="border-t hairline pt-8">
        <div className="border-b hairline pb-4">
          <div className="flex items-center justify-between">
            <p className="editorial-mono text-[10px] uppercase tracking-[.16em] text-[#696862] dark:text-[#9aa0ad]">
              03 / Automated actions
            </p>
            <span className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#6166cf] flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-[#6166cf] animate-pulse" />
              Connected Pipeline
            </span>
          </div>
          <h2 className="editorial-serif mt-2 text-3xl text-[#20201e] dark:text-[#f1f0ea]">
            Quiet work, done at the right moment.
          </h2>
          <p className="mt-2 text-sm text-[#696862] dark:text-[#9aa0ad]">
            What Lively can do automatically during a live conversation.
          </p>
        </div>

        {/* Connected Box by Box Pipeline */}
        <div className="relative pt-6 pb-2">
          {/* Desktop Arrow Connectors */}
          <div className="hidden md:flex absolute top-[44%] left-[33.333%] -translate-x-1/2 -translate-y-1/2 z-20 w-8 h-8 rounded-full bg-white dark:bg-[#151926] border hairline items-center justify-center text-[#6166cf] shadow-xs">
            <ArrowRight size={14} />
          </div>
          <div className="hidden md:flex absolute top-[44%] left-[66.666%] -translate-x-1/2 -translate-y-1/2 z-20 w-8 h-8 rounded-full bg-white dark:bg-[#151926] border hairline items-center justify-center text-[#8c8a82] dark:text-[#697284] shadow-xs">
            <ArrowRight size={14} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
            {/* Box 1: CRM Auto-Sync */}
            <div className="rounded-2xl border hairline bg-white dark:bg-[#121520] p-6 shadow-2xs flex flex-col justify-between transition-all duration-300 hover:border-[#6166cf]/40">
              <div>
                <div className="flex items-center justify-between">
                  <span className="editorial-serif text-3xl text-[#20201e] dark:text-[#f1f0ea]">01</span>
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] editorial-mono uppercase tracking-[.12em] bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200/80 dark:border-emerald-800/60 font-semibold">
                    <CheckCircle2 size={11} />
                    <span>Synced</span>
                  </span>
                </div>

                <h3 className="mt-4 text-xs font-bold uppercase tracking-[.14em] text-[#20201e] dark:text-[#f1f0ea]">
                  CRM Auto-Sync
                </h3>

                <div className="mt-3 p-3.5 rounded-xl bg-[#f7f6f2] dark:bg-[#181c28] border hairline space-y-1.5">
                  <div className="text-sm font-semibold text-[#20201e] dark:text-[#f1f0ea]">
                    {dealState.crm_lead.company || dealState.company || 'Prospective Client'}
                  </div>
                  <div className="text-xs text-[#696862] dark:text-[#9aa0ad]">
                    Deal value: <span className="font-medium text-[#20201e] dark:text-[#e8e6e1]">{dealState.crm_lead.deal_value || dealState.budget || '$50,000 ARR'}</span>
                  </div>
                  <div className="text-[11px] text-[#8c8a82] dark:text-[#717887]">
                    Contact: {dealState.contact_name || dealState.crm_lead.contact_name || 'Lead'} ({dealState.decision_maker || 'Evaluator'})
                  </div>
                </div>
              </div>

              <div className="mt-5 pt-3 border-t hairline">
                <p className="editorial-mono text-[10px] text-[#8c8a82] dark:text-[#717887] leading-relaxed">
                  Trigger — Opportunity updated at {dealState.crm_lead.status || dealState.stage}
                </p>
              </div>
            </div>

            {/* Box 2: Calendar Demo Booking (With Actual Date & Time Display) */}
            <div className={`rounded-2xl border bg-white dark:bg-[#121520] p-6 shadow-2xs flex flex-col justify-between transition-all duration-300 ${
              isDemoSaved
                ? 'border-[#6166cf] dark:border-[#6166cf] ring-1 ring-[#6166cf]/30'
                : 'hairline hover:border-[#6166cf]/40'
            }`}>
              <div>
                <div className="flex items-center justify-between">
                  <span className="editorial-serif text-3xl text-[#20201e] dark:text-[#f1f0ea]">02</span>
                  {isDemoSaved ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] editorial-mono uppercase tracking-[.12em] bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/60 font-semibold animate-pulse">
                      <Lock size={11} />
                      <span>Locked & Confirmed</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] editorial-mono uppercase tracking-[.12em] bg-[#f4f3ed] text-[#696862] dark:bg-[#181c28] dark:text-[#9aa0ad] border hairline">
                      <span>Standing by</span>
                    </span>
                  )}
                </div>

                <h3 className="mt-4 text-xs font-bold uppercase tracking-[.14em] text-[#20201e] dark:text-[#f1f0ea] flex items-center gap-1.5">
                  <span>Demo Booked</span>
                  {isDemoSaved && <CheckCircle2 size={13} className="text-emerald-500" />}
                </h3>

                {isDemoSaved ? (
                  /* Highlighted Actual Date and Time Card */
                  <div className="mt-3 p-3.5 rounded-xl bg-gradient-to-br from-indigo-50/70 to-purple-50/40 dark:from-indigo-950/30 dark:to-purple-950/20 border border-indigo-200/80 dark:border-indigo-800/60 space-y-2">
                    <div className="flex items-start gap-2.5">
                      <Calendar size={16} className="text-[#6166cf] shrink-0 mt-0.5" />
                      <div>
                        <span className="editorial-mono text-[9px] uppercase tracking-[.14em] text-[#6166cf] font-bold block">
                          Confirmed Date & Time
                        </span>
                        <span className="text-sm font-bold text-[#20201e] dark:text-[#f1f0ea] leading-tight block mt-0.5">
                          {demoTime}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 pt-1 text-xs text-[#55544e] dark:text-[#a09e97]">
                      <Mail size={13} className="text-[#6166cf] shrink-0" />
                      <span className="truncate font-medium">{demoEmail}</span>
                      <span className="ml-auto text-[9px] editorial-mono uppercase text-emerald-600 dark:text-emerald-400 font-semibold">
                        Invite Dispatched
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 pt-2">
                      {dealState.scheduled_demo?.meeting_link && (
                        <a
                          href={dealState.scheduled_demo.meeting_link}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#6166cf] hover:bg-[#5257be] text-white text-[11px] font-semibold uppercase tracking-[.08em] transition shadow-xs cursor-pointer"
                        >
                          <Video size={12} />
                          <span>Open Meeting Room</span>
                          <ExternalLink size={11} />
                        </a>
                      )}

                      {calendarBlockUrl && (
                        <a
                          href={calendarBlockUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#181c28] hover:bg-[#f3f2eb] dark:hover:bg-[#202535] text-[#20201e] dark:text-[#f1f0ea] text-[11px] font-semibold uppercase tracking-[.08em] transition shadow-xs cursor-pointer"
                        >
                          <Calendar size={12} className="text-[#6166cf]" />
                          <span>Add to Google Calendar</span>
                          <ExternalLink size={11} />
                        </a>
                      )}
                    </div>
                  </div>
                ) : (
                  /* Standing By Placeholder with Quick Lock Option */
                  <div className="mt-3 p-3.5 rounded-xl bg-[#f7f6f2] dark:bg-[#181c28] border hairline space-y-2.5">
                    <p className="text-xs leading-relaxed text-[#696862] dark:text-[#9aa0ad]">
                      Standing by for buyer confirmation. Lively listens for scheduling intent, extracting exact date, time, and attendee email.
                    </p>
                    <p className="text-[11px] text-[#8c8a82] dark:text-[#717887] italic">
                      Slot will lock in automatically upon buyer interest.
                    </p>
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={() => handleQuickLock('Thursday at 2:00 PM EST')}
                        disabled={isBookingManual}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#6166cf] hover:bg-[#5257be] text-white text-[11px] font-semibold uppercase tracking-[.08em] transition shadow-xs disabled:opacity-50 cursor-pointer"
                      >
                        <Lock size={12} />
                        <span>{isBookingManual ? 'Locking in slot...' : 'Lock in Thursday 2 PM'}</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-5 pt-3 border-t hairline">
                <p className="editorial-mono text-[10px] text-[#8c8a82] dark:text-[#717887] leading-relaxed">
                  Trigger — Buyer confirms demo interest
                </p>
              </div>
            </div>

            {/* Box 3: Human Escalation */}
            <div className={`rounded-2xl border bg-white dark:bg-[#121520] p-6 shadow-2xs flex flex-col justify-between transition-all duration-300 ${
              escalated
                ? 'border-amber-500/80 dark:border-amber-500/60 ring-1 ring-amber-500/20'
                : 'hairline hover:border-[#6166cf]/40'
            }`}>
              <div>
                <div className="flex items-center justify-between">
                  <span className="editorial-serif text-3xl text-[#20201e] dark:text-[#f1f0ea]">03</span>
                  {escalated ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] editorial-mono uppercase tracking-[.12em] bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border border-amber-200 dark:border-amber-800 font-semibold">
                      <ShieldAlert size={11} />
                      <span>Handoff Ready</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] editorial-mono uppercase tracking-[.12em] bg-[#f4f3ed] text-[#696862] dark:bg-[#181c28] dark:text-[#9aa0ad] border hairline">
                      <span>Standing by</span>
                    </span>
                  )}
                </div>

                <h3 className="mt-4 text-xs font-bold uppercase tracking-[.14em] text-[#20201e] dark:text-[#f1f0ea]">
                  Human Escalation
                </h3>

                <div className="mt-3 p-3.5 rounded-xl bg-[#f7f6f2] dark:bg-[#181c28] border hairline space-y-1.5">
                  <p className="text-xs leading-relaxed text-[#696862] dark:text-[#9aa0ad]">
                    {escalated
                      ? 'Account executive bridge prepared. Full conversation context and BANT scorecard packaged.'
                      : 'A human partner can join when an enterprise question or complex bespoke moment needs human guidance.'}
                  </p>
                  <p className="text-[11px] text-[#8c8a82] dark:text-[#717887]">
                    Target: Enterprise AE · Sub-15s response SLA
                  </p>
                </div>
              </div>

              <div className="mt-5 pt-3 border-t hairline">
                <p className="editorial-mono text-[10px] text-[#8c8a82] dark:text-[#717887] leading-relaxed">
                  Trigger — Enterprise request or explicit handoff
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Hero layout for Live Sales Cockpit
  const stages = [
    { title: 'CRM auto-synced', detail: `${dealState.crm_lead.company} · ${dealState.crm_lead.deal_value}`, status: 'Synced', trigger: `Opportunity updated at ${dealState.crm_lead.status || dealState.stage}` },
    {
      title: 'Demo booked',
      detail: dealState.scheduled_demo ? `Reserved ${dealState.scheduled_demo.time} for ${dealState.scheduled_demo.email}` : 'Standing by for a confirmed time.',
      status: demoBooked ? 'Booked' : 'Standing by',
      trigger: 'Buyer confirms demo interest',
      link: dealState.scheduled_demo?.meeting_link,
      calendarLink: dealState.scheduled_demo?.google_calendar_link
    },
    { title: 'Human escalation', detail: escalated ? 'Handoff is ready for the account executive.' : 'A human partner can join when the moment calls for it.', status: escalated ? 'Active' : 'Standing by', trigger: dealState.action_items[dealState.action_items.length - 1] || 'Enterprise request or explicit handoff' },
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
                              Open meeting <ExternalLink size={11} />
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
