import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Phone, Pause, Play, RefreshCw, Users, Bot, UserCheck,
  PhoneOff, Shield, Activity, AlertTriangle, Plus, Trash2,
} from 'lucide-react';
import {
  createDialerCampaign, startDialerCampaign, pauseDialerCampaign,
  resetDialerBreaker, getDialerCampaign, LeadInput,
} from '../services/api';

// --------------------------------------------------------------------------- //
// Types                                                                         //
// --------------------------------------------------------------------------- //

interface Lead {
  id:           string;
  name:         string;
  phone:        string;
  company:      string;
  status:       string;
  attempt:      number;
  handler:      string | null;
}

interface CampaignSnapshot {
  campaign_id:      string;
  name:             string;
  state:            string;
  total_leads:      number;
  queued:           number;
  dialing:          number;
  answered_ai:      number;
  answered_human:   number;
  no_answer:        number;
  dropped:          number;
  completed:        number;
  connect_rate:     number;
  proposed_dials:   number;
  authorised_dials: number;
  abandon_rate:     number;
  ai_slots_used:    number;
  ai_slots_total:   number;
  leads:            Lead[];
  safety_paused:    boolean;
  circuit_breaker:  string;
}

// --------------------------------------------------------------------------- //
// Status badge helpers                                                          //
// --------------------------------------------------------------------------- //

const LEAD_STATUS_CONFIG: Record<string, { label: string; textClass: string; bgClass: string }> = {
  queued:          { label: 'Queued',        textClass: 'text-[#8c8a82] dark:text-[#a1a1aa]', bgClass: 'bg-[#f0efea] dark:bg-[#1a1b22]' },
  dialing:         { label: 'Dialing…',      textClass: 'text-[#20201e] dark:text-[#f4f4f5]', bgClass: 'bg-neutral-100 dark:bg-neutral-800' },
  answered_ai:     { label: 'AI Agent',      textClass: 'text-[#20201e] dark:text-[#f1f0ea]', bgClass: 'bg-[#ebe9e1] dark:bg-[#252830]' },
  answered_human:  { label: 'Human Rep',     textClass: 'text-[#52525b] dark:text-[#d4d4d8]', bgClass: 'bg-[#f0efea] dark:bg-[#1a1b22]' },
  no_answer:       { label: 'No Answer',     textClass: 'text-[#71717a] dark:text-[#a1a1aa]', bgClass: 'bg-[#f4f3ef] dark:bg-[#191a20]' },
  busy:            { label: 'Busy',          textClass: 'text-[#71717a] dark:text-[#a1a1aa]', bgClass: 'bg-[#f4f3ef] dark:bg-[#191a20]' },
  dropped:         { label: 'Dropped',       textClass: 'text-[#71717a] dark:text-[#a1a1aa]', bgClass: 'bg-[#f4f3ef] dark:bg-[#191a20]' },
  completed:       { label: 'Completed',     textClass: 'text-[#71717a] dark:text-[#a1a1aa]', bgClass: 'bg-[#f0efea] dark:bg-[#1a1b22]' },
};

const CB_CONFIG: Record<string, { label: string; textClass: string; bgClass: string }> = {
  closed:    { label: 'Circuit Closed',    textClass: 'text-[#696862] dark:text-[#a1a1aa]', bgClass: 'bg-[#f0efea] dark:bg-[#1a1c23]' },
  half_open: { label: 'Circuit Half-Open', textClass: 'text-[#71717a] dark:text-[#d4d4d8]', bgClass: 'bg-[#f0efea] dark:bg-[#1a1c23]' },
  open:      { label: 'Circuit Open ⚠️',   textClass: 'text-[#20201e] dark:text-[#f4f4f5]', bgClass: 'bg-[#e5e4de] dark:bg-[#252832]' },
};

// --------------------------------------------------------------------------- //
// Sub-components                                                                //
// --------------------------------------------------------------------------- //

const StatCard: React.FC<{ label: string; value: number | string; icon: React.FC<any>; sub?: string }> = ({
  label, value, icon: Icon, sub,
}) => (
  <div className="rounded-xl border hairline bg-white dark:bg-[#141416] p-3.5 flex flex-col gap-1 shadow-xs">
    <div className="flex items-center justify-between">
      <span className="text-[9.5px] editorial-mono uppercase tracking-[.14em] text-[#8c8a82] dark:text-[#9aa0ad]">{label}</span>
      <Icon size={13} className="text-[#696862] dark:text-[#a1a1aa]" />
    </div>
    <span className="text-2xl font-bold text-[#20201e] dark:text-[#f1f0ea]">{value}</span>
    {sub && <span className="text-[9.5px] text-[#a7a59d] dark:text-[#71717a]">{sub}</span>}
  </div>
);

const PacingBar: React.FC<{ proposed: number; authorised: number; reason?: string }> = ({
  proposed, authorised, reason,
}) => {
  const max = Math.max(proposed, 20);
  return (
    <div className="rounded-xl border hairline bg-white dark:bg-[#141416] px-4 py-3 space-y-2 shadow-xs">
      <p className="text-[9.5px] editorial-mono uppercase tracking-[.16em] text-[#8c8a82] dark:text-[#9aa0ad]">
        Safety Authorisation
      </p>
      <p className="text-xs font-bold text-[#20201e] dark:text-[#f1f0ea]">
        Proposed {proposed} → Authorised {authorised}
      </p>
      <div className="relative h-2.5 rounded-full bg-[#f0efea] dark:bg-[#1a1b20] overflow-hidden">
        <div
          className="absolute left-0 top-0 h-full rounded-full transition-all duration-700"
          style={{ width: `${Math.min(100,(proposed/max)*100)}%`, background: 'rgba(32,32,30,0.2)' }}
        />
        <div
          className="absolute left-0 top-0 h-full rounded-full transition-all duration-700"
          style={{
            width: `${Math.min(100,(authorised/max)*100)}%`,
            background: 'linear-gradient(90deg, #18181b, #52525b)',
          }}
        />
      </div>
      {reason && (
        <p className="text-[10px] text-[#696862] dark:text-[#9aa0ad] leading-relaxed">{reason}</p>
      )}
    </div>
  );
};

// --------------------------------------------------------------------------- //
// Default leads for the demo harness                                            //
// --------------------------------------------------------------------------- //

const DEMO_LEADS: LeadInput[] = [
  { name: 'Priya Mehta',      phone: '+91 98765 43210', company: 'Nexus Analytics' },
  { name: 'James Caldwell',   phone: '+1 415 555 0100', company: 'Bridgepoint SaaS' },
  { name: 'Aisha Okonkwo',    phone: '+44 20 7946 0100', company: 'Clarity Health' },
  { name: 'Lucas Ferreira',   phone: '+55 11 9 9876 5432', company: 'VenturaSoft' },
  { name: 'Sofia Lindqvist',  phone: '+46 70 123 4567', company: 'Eko Commerce' },
  { name: 'Raj Patel',        phone: '+91 80 4567 8901', company: 'CloudBase India' },
  { name: 'Mei-Lin Chen',     phone: '+86 138 0013 8000', company: 'Sino Digital' },
  { name: 'Carlos Ruiz',      phone: '+34 612 345 678', company: 'IberTech Group' },
];

// --------------------------------------------------------------------------- //
// Main component                                                                //
// --------------------------------------------------------------------------- //

export const SmartDialerPanel: React.FC = () => {
  const [campaign,   setCampaign]   = useState<CampaignSnapshot | null>(null);
  const [creating,   setCreating]   = useState(false);
  const [busy,       setBusy]       = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [leads,      setLeads]      = useState<LeadInput[]>(DEMO_LEADS);
  const [newName,    setNewName]    = useState('');
  const [newPhone,   setNewPhone]   = useState('');
  const [newCompany, setNewCompany] = useState('');
  const [aiSlots,    setAiSlots]    = useState(3);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async (id: string) => {
    try {
      const snap = await getDialerCampaign(id);
      setCampaign(snap);
    } catch {
      // Silent polling failure
    }
  }, []);

  useEffect(() => {
    if (campaign?.campaign_id && campaign.state === 'running') {
      pollRef.current = setInterval(() => refresh(campaign.campaign_id), 2500);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [campaign?.campaign_id, campaign?.state, refresh]);

  const handleCreate = async () => {
    setCreating(false);
    setBusy(true);
    setError(null);
    try {
      const res = await createDialerCampaign('Demo Outbound Campaign', leads, aiSlots);
      setCampaign(res.data as CampaignSnapshot);
    } catch (e: any) {
      setError(e.message || 'Failed to create campaign');
    } finally {
      setBusy(false);
    }
  };

  const handleStart = async () => {
    if (!campaign) return;
    setBusy(true);
    try {
      await startDialerCampaign(campaign.campaign_id);
      await refresh(campaign.campaign_id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handlePause = async () => {
    if (!campaign) return;
    setBusy(true);
    try {
      await pauseDialerCampaign(campaign.campaign_id);
      await refresh(campaign.campaign_id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleResetBreaker = async () => {
    if (!campaign) return;
    setBusy(true);
    try {
      await resetDialerBreaker(campaign.campaign_id);
      await refresh(campaign.campaign_id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleAddLead = () => {
    if (!newName.trim()) return;
    setLeads(prev => [...prev, { name: newName.trim(), phone: newPhone.trim(), company: newCompany.trim() }]);
    setNewName(''); setNewPhone(''); setNewCompany('');
  };

  const cb = campaign ? CB_CONFIG[campaign.circuit_breaker] ?? CB_CONFIG.closed : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b hairline pb-5">
        <p className="editorial-mono text-[10px] uppercase tracking-[.16em] text-[#696862] dark:text-[#9aa0ad]">
          04 / SmartDialer
        </p>
        <h2 className="editorial-serif mt-2 text-3xl text-[#20201e] dark:text-[#f1f0ea]">
          Outbound Intelligence Engine
        </h2>
        <p className="mt-1.5 text-sm text-[#696862] dark:text-[#9aa0ad] max-w-xl">
          Statistical pacing (binomial quantile) proposes a dial count.
          The Safety Controller authorises the final number. AI agents handle overflow answers.
        </p>
        <div className="mt-2 flex items-center gap-2 text-[10px] editorial-mono text-[#8c8a82]">
          <span className="px-2 py-0.5 rounded bg-[#f0efea] dark:bg-[#18191e]">Pacing proposes</span>
          <span>→</span>
          <span className="px-2 py-0.5 rounded bg-[#f0efea] dark:bg-[#18191e]">Safety authorises</span>
          <span>→</span>
          <span className="px-2 py-0.5 rounded bg-[#f0efea] dark:bg-[#18191e]">AI agents handle overflow</span>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-red-50 dark:bg-red-950/20 border border-red-200/60 text-sm text-red-600 dark:text-red-400">
          <AlertTriangle size={14} />
          <span>{error}</span>
        </div>
      )}

      {!campaign ? (
        /* ---------------------------------------------------------------- Setup */
        <div className="rounded-2xl border hairline bg-white dark:bg-[#141416] p-6 space-y-6">
          <div>
            <h3 className="text-sm font-bold text-[#20201e] dark:text-[#f1f0ea] mb-1">Lead list</h3>
            <p className="text-xs text-[#696862] dark:text-[#9aa0ad] mb-4">
              {leads.length} leads loaded · Simulated calls (no real phone network)
            </p>

            {/* Lead table */}
            <div className="rounded-xl border hairline overflow-hidden mb-4">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-[#f7f6f2] dark:bg-[#18191e] border-b hairline">
                    <th className="text-left px-3 py-2 text-[#696862] dark:text-[#9aa0ad] font-medium">Name</th>
                    <th className="text-left px-3 py-2 text-[#696862] dark:text-[#9aa0ad] font-medium">Phone</th>
                    <th className="text-left px-3 py-2 text-[#696862] dark:text-[#9aa0ad] font-medium">Company</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {leads.map((l, i) => (
                    <tr key={i} className="border-b hairline last:border-0 hover:bg-[#faf9f7] dark:hover:bg-[#18191e]">
                      <td className="px-3 py-2 font-medium text-[#20201e] dark:text-[#e8e6e1]">{l.name}</td>
                      <td className="px-3 py-2 editorial-mono text-[10px] text-[#8c8a82]">{l.phone || '—'}</td>
                      <td className="px-3 py-2 text-[#696862] dark:text-[#9aa0ad]">{l.company || '—'}</td>
                      <td className="px-3 py-2 text-right">
                        <button onClick={() => setLeads(prev => prev.filter((_, j) => j !== i))}
                          className="text-[#c8c6c0] hover:text-red-400 transition">
                          <Trash2 size={12} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Add lead */}
            <div className="flex items-center gap-2 flex-wrap">
              <input id="dialer-lead-name" placeholder="Name" value={newName}
                onChange={e => setNewName(e.target.value)}
                className="flex-1 min-w-[120px] px-3 py-1.5 rounded-lg border hairline text-xs bg-white dark:bg-[#18191e] text-[#20201e] dark:text-[#e8e6e1]" />
              <input id="dialer-lead-phone" placeholder="Phone" value={newPhone}
                onChange={e => setNewPhone(e.target.value)}
                className="w-36 px-3 py-1.5 rounded-lg border hairline text-xs bg-white dark:bg-[#18191e] text-[#20201e] dark:text-[#e8e6e1]" />
              <input id="dialer-lead-company" placeholder="Company" value={newCompany}
                onChange={e => setNewCompany(e.target.value)}
                className="flex-1 min-w-[120px] px-3 py-1.5 rounded-lg border hairline text-xs bg-white dark:bg-[#18191e] text-[#20201e] dark:text-[#e8e6e1]" />
              <button onClick={handleAddLead}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#18191e] text-xs text-[#20201e] dark:text-[#e8e6e1] hover:border-[#20201e] dark:hover:border-white/40 transition">
                <Plus size={12} /> Add
              </button>
            </div>
          </div>

          {/* AI slots */}
          <div className="flex items-center gap-4">
            <label className="text-sm text-[#55544e] dark:text-[#a09e97]">AI agent slots</label>
            <input id="dialer-ai-slots" type="range" min={1} max={10} value={aiSlots}
              onChange={e => setAiSlots(Number(e.target.value))}
              className="w-28 accent-[#20201e] dark:accent-[#e8e6e1]" />
            <span className="text-sm font-bold text-[#20201e] dark:text-[#e8e6e1] w-6">{aiSlots}</span>
          </div>

          {/* Launch button */}
          <button
            id="dialer-launch-btn"
            onClick={handleCreate}
            disabled={busy || leads.length === 0}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#141416] hover:bg-[#222227] text-white dark:bg-[#18191e] dark:hover:bg-[#252730] dark:text-[#f4f3ef] border border-black/20 dark:border-white/15 text-sm font-semibold uppercase tracking-[.08em] transition shadow-sm hover:shadow active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <Phone size={15} />
            {busy ? 'Creating campaign…' : `Launch campaign · ${leads.length} leads`}
          </button>
        </div>
      ) : (
        /* ---------------------------------------------------------------- Live dashboard */
        <div className="space-y-5">
          {/* Controls row */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-bold text-[#20201e] dark:text-[#f1f0ea]">{campaign.name}</h3>
              <span className={`editorial-mono text-[9.5px] uppercase tracking-[.12em] px-2 py-0.5 rounded-full ${
                campaign.state === 'running'   ? 'bg-[#141416] text-white dark:bg-[#f1f0ea] dark:text-[#141416]' :
                campaign.state === 'paused'    ? 'bg-neutral-200 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300' :
                'bg-[#f0efea] dark:bg-[#1a1b22] text-[#8c8a82] dark:text-[#a1a1aa]'
              }`}>
                {campaign.state}
              </span>
              {cb && (
                <span className={`editorial-mono text-[9px] uppercase tracking-[.1em] px-2 py-0.5 rounded-full border hairline ${cb.bgClass} ${cb.textClass}`}>
                  {cb.label}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {campaign.circuit_breaker !== 'closed' && (
                <button onClick={handleResetBreaker} disabled={busy}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-[#f0efea] hover:bg-[#e4e2d8] dark:bg-[#1e2028] dark:hover:bg-[#252834] text-[#20201e] dark:text-[#f1f0ea] text-[11px] font-semibold uppercase tracking-[.08em] transition disabled:opacity-50">
                  <RefreshCw size={12} /> Reset Breaker
                </button>
              )}
              {campaign.state !== 'completed' && (
                campaign.state === 'running' ? (
                  <button onClick={handlePause} disabled={busy}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#20201e] dark:bg-[#e8e6e1] text-white dark:text-[#20201e] text-[11px] font-semibold uppercase tracking-[.08em] transition disabled:opacity-50">
                    <Pause size={12} /> Pause
                  </button>
                ) : (
                  <button onClick={handleStart} disabled={busy}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#141416] hover:bg-[#222227] text-white dark:bg-[#18191e] dark:hover:bg-[#252730] dark:text-[#f4f3ef] border border-black/20 dark:border-white/15 text-[11px] font-semibold uppercase tracking-[.08em] transition shadow-xs active:scale-95 disabled:opacity-50 cursor-pointer">
                    <Play size={12} /> {campaign.state === 'idle' ? 'Start' : 'Resume'}
                  </button>
                )
              )}
              <button onClick={() => setCampaign(null)} disabled={busy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline text-[11px] text-[#696862] dark:text-[#9aa0ad] hover:border-[#20201e] dark:hover:border-white/40 transition">
                New campaign
              </button>
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Dialing" value={campaign.dialing} icon={Phone}
              sub={`of ${campaign.total_leads} leads`} />
            <StatCard label="AI Handled" value={campaign.answered_ai} icon={Bot}
              sub={`${campaign.ai_slots_used}/${campaign.ai_slots_total} slots used`} />
            <StatCard label="Human Rep" value={campaign.answered_human} icon={UserCheck} />
            <StatCard label="No Answer" value={campaign.no_answer + campaign.dropped} icon={PhoneOff}
              sub={`abandon ${(campaign.abandon_rate * 100).toFixed(1)}%`} />
          </div>

          {/* Pacing trace */}
          <PacingBar
            proposed={campaign.proposed_dials}
            authorised={campaign.authorised_dials}
            reason={`Connect rate ${(campaign.connect_rate * 100).toFixed(0)}% · ${campaign.ai_slots_total} AI slot(s) · ${campaign.queued} lead(s) queued`}
          />

          {/* Safety alert */}
          {campaign.safety_paused && (
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[#f4f3ee] dark:bg-[#181920] border hairline text-xs text-[#52525b] dark:text-[#a1a1aa]">
              <Shield size={14} className="text-[#8c8a82]" />
              <span>Safety Controller paused dialing — abandon rate or circuit breaker triggered.</span>
            </div>
          )}

          {/* Lead queue */}
          <div>
            <p className="text-[9.5px] editorial-mono uppercase tracking-[.16em] text-[#8c8a82] mb-2">
              Lead queue ({campaign.leads.length})
            </p>
            <div className="rounded-xl border hairline overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-[#f7f6f2] dark:bg-[#18191e] border-b hairline">
                    <th className="text-left px-3 py-2 text-[#696862] dark:text-[#9aa0ad] font-medium">Name</th>
                    <th className="text-left px-3 py-2 text-[#696862] dark:text-[#9aa0ad] font-medium hidden sm:table-cell">Company</th>
                    <th className="text-left px-3 py-2 text-[#696862] dark:text-[#9aa0ad] font-medium">Status</th>
                    <th className="text-right px-3 py-2 text-[#696862] dark:text-[#9aa0ad] font-medium hidden sm:table-cell">Attempt</th>
                  </tr>
                </thead>
                <tbody>
                  {campaign.leads.slice(0, 20).map(lead => {
                    const sc = LEAD_STATUS_CONFIG[lead.status] ?? LEAD_STATUS_CONFIG.queued;
                    return (
                      <tr key={lead.id} className="border-b hairline last:border-0 hover:bg-[#faf9f7] dark:hover:bg-[#18191e] transition">
                        <td className="px-3 py-2 font-medium text-[#20201e] dark:text-[#e8e6e1]">{lead.name}</td>
                        <td className="px-3 py-2 text-[#696862] dark:text-[#9aa0ad] hidden sm:table-cell">{lead.company || '—'}</td>
                        <td className="px-3 py-2">
                          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9.5px] editorial-mono uppercase tracking-[.08em] font-semibold ${sc.bgClass} ${sc.textClass}`}>
                            {lead.status === 'dialing' && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />}
                            {sc.label}
                            {lead.handler === 'ai' && ' · AI'}
                            {lead.handler === 'human' && ' · Human'}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right editorial-mono text-[10px] text-[#8c8a82] hidden sm:table-cell">
                          #{lead.attempt}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Live connect rate bar */}
          <div className="rounded-xl border hairline bg-white dark:bg-[#141416] px-4 py-3 space-y-2 shadow-xs">
            <div className="flex items-center justify-between">
              <p className="text-[9.5px] editorial-mono uppercase tracking-[.16em] text-[#8c8a82]">Rolling connect rate</p>
              <span className="text-xs font-bold text-[#20201e] dark:text-[#f1f0ea]">
                {(campaign.connect_rate * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-2 rounded-full bg-[#f0efea] dark:bg-[#1a1b20] overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{ width: `${(campaign.connect_rate * 100).toFixed(0)}%`, background: 'linear-gradient(90deg, #18181b, #52525b)' }}
              />
            </div>
            <p className="text-[9px] text-[#a7a59d] dark:text-[#5a6175]">
              Updated on each answered / missed call. Drives next pacing recommendation.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
