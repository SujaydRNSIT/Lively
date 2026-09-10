import React, { useState } from 'react';
import { Scale, CheckCircle2, Clock, XCircle, ChevronRight, Shield, TrendingDown } from 'lucide-react';
import { approveConcession, proposeConcession } from '../services/api';

interface ConcessionRecord {
  id:                       string;
  proposed_pct:             number;
  authorised_pct:           number;
  status:                   'approved' | 'pending_manager' | 'refused' | 'expired';
  reason:                   string;
  trade:                    string | null;
  manager_approval_required: boolean;
  approved_by:              string | null;
  label:                    string;
  bound_by:                 string;
  channel_name:             string;
  expires_at:               number;
}

interface DealDeskPanelProps {
  channelName: string;
  concession:  ConcessionRecord | null;
  /** DEAL_DESK_UPDATE events push a new record here */
  onUpdate?:   (record: ConcessionRecord) => void;
}

const STATUS_CONFIG: Record<string, { icon: React.FC<any>; color: string; bg: string; border: string; label: string }> = {
  approved: {
    icon:   CheckCircle2,
    color:  '#20201e',
    bg:     'bg-[#f0efea] dark:bg-[#1a1c24]',
    border: 'border-[#d7d5ce] dark:border-[#2a2e3d]',
    label:  'Approved',
  },
  pending_manager: {
    icon:   Clock,
    color:  '#52525b',
    bg:     'bg-[#f7f6f2] dark:bg-[#161822]',
    border: 'border-[#e5e4de] dark:border-[#262a38]',
    label:  'Manager Approval Required',
  },
  refused: {
    icon:   XCircle,
    color:  '#71717a',
    bg:     'bg-[#f7f6f2] dark:bg-[#161822]',
    border: 'border-[#e5e4de] dark:border-[#262a38]',
    label:  'Refused',
  },
  expired: {
    icon:   XCircle,
    color:  '#8c8a82',
    bg:     'bg-[#f7f6f2] dark:bg-[#161822]',
    border: 'border-[#e5e4de] dark:border-[#262a38]',
    label:  'Expired',
  },
};

const TRADE_LABELS: Record<string, string> = {
  annual:     'Annual billing commitment',
  case_study: 'Reference customer agreement',
  seats:      'Seat count upgrade',
};

/** Visual bar showing proposed vs authorised discount */
const DiscountBar: React.FC<{ proposed: number; authorised: number; status: string }> = ({
  proposed,
  authorised,
  status,
}) => {
  const MAX = 25;   // hard ceiling matches backend policy
  const proposedW  = Math.min(100, (proposed  / MAX) * 100);
  const authorisedW = status === 'refused' ? 0 : Math.min(100, (authorised / MAX) * 100);

  return (
    <div className="mt-3 space-y-1.5">
      <div className="flex items-center justify-between text-[9.5px] editorial-mono uppercase tracking-[.14em] text-[#8c8a82]">
        <span>0%</span>
        <span>Hard ceiling {MAX}%</span>
      </div>
      <div className="relative h-3 rounded-full bg-[#f0efea] dark:bg-[#1a1d2a] overflow-hidden">
        {/* Proposed bar */}
        <div
          className="absolute left-0 top-0 h-full rounded-full transition-all duration-700"
          style={{
            width:      `${proposedW}%`,
            background: 'linear-gradient(90deg, rgba(32,32,30,0.3), rgba(32,32,30,0.6))',
          }}
        />
        {/* Authorised bar */}
        <div
          className="absolute left-0 top-0 h-full rounded-full transition-all duration-700"
          style={{
            width:      `${authorisedW}%`,
            background: status === 'approved'
              ? 'linear-gradient(90deg, #10b981, #059669)'
              : status === 'pending_manager'
              ? 'linear-gradient(90deg, #f59e0b, #d97706)'
              : 'transparent',
          }}
        />
      </div>
      <div className="flex items-center gap-4 text-[10px] text-[#696862] dark:text-[#9aa0ad]">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-1.5 rounded-sm bg-[#20201e]/40 dark:bg-white/40" />
          Proposed {proposed}%
        </span>
        {status !== 'refused' && (
          <span className="flex items-center gap-1">
            <span
              className="inline-block w-2.5 h-1.5 rounded-sm"
              style={{ background: status === 'approved' ? '#10b981' : '#f59e0b' }}
            />
            {status === 'approved' ? 'Authorised' : 'Max if approved'} {authorised}%
          </span>
        )}
      </div>
    </div>
  );
};

/** Demo sandbox — trigger a concession proposal directly from the UI */
const ProposeSandbox: React.FC<{
  channelName: string;
  onProposed: (rec: ConcessionRecord) => void;
}> = ({ channelName, onProposed }) => {
  const [pct,   setPct]   = useState(20);
  const [trade, setTrade] = useState('none');
  const [busy,  setBusy]  = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePropose = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await proposeConcession(channelName, pct, trade === 'none' ? undefined : trade);
      onProposed(res.data as ConcessionRecord);
    } catch (e: any) {
      setError(e.message || 'Failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 rounded-xl border hairline bg-[#f7f6f2] dark:bg-[#141416] p-4 space-y-3">
      <p className="text-[9.5px] editorial-mono uppercase tracking-[.16em] text-[#8c8a82]">
        Sandbox — propose a concession
      </p>
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs text-[#55544e] dark:text-[#a09e97]">Discount</label>
          <div className="flex items-center gap-1.5">
            <input
              id="deal-desk-pct"
              type="range"
              min={5} max={30} step={1}
              value={pct}
              onChange={e => setPct(Number(e.target.value))}
              className="w-24 accent-[#20201e] dark:accent-[#e8e6e1]"
            />
            <span className="text-xs font-bold text-[#20201e] dark:text-[#e8e6e1] w-8">{pct}%</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-[#55544e] dark:text-[#a09e97]">Trade requested</label>
          <select
            id="deal-desk-trade"
            value={trade}
            onChange={e => setTrade(e.target.value)}
            className="px-2.5 py-1 rounded-lg border hairline text-xs bg-white dark:bg-[#18191e] text-[#20201e] dark:text-[#e8e6e1]"
          >
            <option value="none">None</option>
            {Object.entries(TRADE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <button
          id="deal-desk-propose-btn"
          onClick={handlePropose}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#18191e] hover:bg-[#f0efea] dark:hover:bg-[#20222a] text-xs font-medium text-[#20201e] dark:text-[#e8e6e1] transition disabled:opacity-50 cursor-pointer"
        >
          <Scale size={12} />
          {busy ? 'Calculating…' : 'Calculate & Propose'}
        </button>
      </div>
      {error && <p className="text-xs text-red-500 dark:text-red-400">{error}</p>}
    </div>
  );
};

export const DealDeskPanel: React.FC<DealDeskPanelProps> = ({
  channelName,
  concession,
  onUpdate,
}) => {
  const [busy,  setBusy]  = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = async () => {
    if (!concession) return;
    setBusy(true);
    setError(null);
    try {
      const res = await approveConcession(channelName, concession.id);
      onUpdate?.(res.data as ConcessionRecord);
    } catch (e: any) {
      setError(e.message || 'Failed to approve');
    } finally {
      setBusy(false);
    }
  };

  const cfg = concession ? STATUS_CONFIG[concession.status] ?? STATUS_CONFIG.refused : null;

  return (
    <div className="rounded-2xl border hairline bg-white dark:bg-[#141416] shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b hairline">
        <div className="flex items-center gap-2">
          <Scale size={14} className="text-[#20201e] dark:text-[#e8e6e1]" />
          <span className="text-[10px] editorial-mono uppercase tracking-[.18em] text-[#696862] dark:text-[#9aa0ad] font-semibold">
            Deal Desk
          </span>
          <span className="text-[9px] editorial-mono px-1.5 py-0.5 rounded bg-[#f0efea] dark:bg-[#1a1b22] text-[#8c8a82]">
            LLM proposes · Policy decides
          </span>
        </div>
        {cfg && (
          <span
            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9.5px] editorial-mono uppercase tracking-[.1em] border ${cfg.bg} ${cfg.border}`}
            style={{ color: cfg.color }}
          >
            <cfg.icon size={10} />
            {cfg.label}
          </span>
        )}
      </div>

      <div className="px-4 pt-4 pb-4">
        {!concession ? (
          <div className="py-6 text-center">
            <Shield size={22} className="mx-auto text-[#c8c6c0] dark:text-[#3a3f52] mb-2" />
            <p className="text-xs text-[#a7a59d] dark:text-[#5a6175] italic">
              No concession proposed yet.
            </p>
            <p className="text-[10px] text-[#c8c6c0] dark:text-[#4a5168] mt-1">
              Agent calls <code className="font-mono">propose_concession</code> when a buyer negotiates on price.
            </p>
          </div>
        ) : (
          <>
            {/* Main label */}
            <div className="rounded-xl border hairline bg-[#f7f6f2] dark:bg-[#0a0c12] px-4 py-3">
              <p className="text-sm font-bold text-[#20201e] dark:text-[#f1f0ea] leading-snug">
                {concession.label}
              </p>
              <p className="mt-1 text-[10.5px] text-[#696862] dark:text-[#9aa0ad] flex items-start gap-1.5">
                <Shield size={11} className="shrink-0 mt-0.5 text-[#20201e] dark:text-[#e8e6e1]" />
                Bound by: {concession.bound_by}
              </p>
            </div>

            {/* Visual bar */}
            <DiscountBar
              proposed={concession.proposed_pct}
              authorised={concession.authorised_pct}
              status={concession.status}
            />

            {/* Trade commitment */}
            {concession.trade && (
              <div className="mt-3 flex items-start gap-2 text-[11px] text-[#696862] dark:text-[#9aa0ad]">
                <TrendingDown size={13} className="shrink-0 mt-0.5 text-[#20201e] dark:text-[#e8e6e1]" />
                <span>Trade committed: <strong className="text-[#20201e] dark:text-[#e8e6e1]">{TRADE_LABELS[concession.trade] ?? concession.trade}</strong></span>
              </div>
            )}

            {/* Policy reasoning */}
            <div className="mt-3 flex items-start gap-2 text-[10.5px] text-[#8c8a82]">
              <ChevronRight size={12} className="shrink-0 mt-0.5" />
              <span>{concession.reason}</span>
            </div>

            {/* Manager approval button */}
            {concession.status === 'pending_manager' && (
              <div className="mt-4 rounded-xl border border-amber-300/50 dark:border-amber-700/40 bg-amber-50 dark:bg-amber-950/20 px-4 py-3">
                <p className="text-xs font-semibold text-amber-700 dark:text-amber-400 mb-2">
                  ⚠️ This concession is above agent authority — manager approval required.
                </p>
                <button
                  id="deal-desk-approve-btn"
                  onClick={handleApprove}
                  disabled={busy}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-[11px] font-semibold uppercase tracking-[.08em] transition shadow-sm disabled:opacity-50"
                >
                  <CheckCircle2 size={13} />
                  {busy ? 'Approving…' : `Approve ${concession.authorised_pct}% discount`}
                </button>
                {error && <p className="mt-2 text-[11px] text-red-500">{error}</p>}
              </div>
            )}

            {/* Approved confirmation */}
            {concession.status === 'approved' && (
              <div className="mt-3 flex items-center gap-2 text-[11px] text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 size={13} />
                <span>
                  Authorised {concession.authorised_pct}%
                  {concession.approved_by ? ` · approved by ${concession.approved_by}` : ' · within agent authority'}
                </span>
              </div>
            )}
          </>
        )}

        {/* Sandbox for demo harness */}
        <ProposeSandbox
          channelName={channelName}
          onProposed={rec => onUpdate?.(rec)}
        />
      </div>
    </div>
  );
};
