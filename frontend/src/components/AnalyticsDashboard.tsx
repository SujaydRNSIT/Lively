import React, { useEffect, useState } from 'react';
import { LatencyStats, DealState } from '../types';
import { API_BASE } from '../services/api';

// Nothing is shown until real turns have been measured.
const EMPTY: LatencyStats = { total_turns: 0, measured: false, ttft_p50_ms: null, ttft_p95_ms: null, ttft_mean_ms: null, ttft_min_ms: null, total_turn_p50_ms: null, total_turn_p95_ms: null, model_breakdown: { groq: 0, nvidia_nim: 0, builtin_fallback: 0 } };
const ms = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v)} ms`);

export const AnalyticsDashboard: React.FC<{ dealState: DealState }> = ({ dealState }) => {
  const [stats, setStats] = useState<LatencyStats>(EMPTY);
  useEffect(() => { fetch(`${API_BASE}/telemetry/latency-stats`).then(r => r.json()).then(j => j.data && setStats(j.data)).catch(() => {}); }, [dealState]);

  const measures = [['TTFT / p50', ms(stats.ttft_p50_ms)], ['TTFT / p95', ms(stats.ttft_p95_ms)], ['Response / p50', ms(stats.total_turn_p50_ms)], ['Turns measured', `${stats.total_turns}`]];
  const badge = !stats.measured || stats.ttft_p50_ms == null
    ? '○ No turns measured yet'
    : stats.ttft_p50_ms < 300 ? `● p50 TTFT under 300 ms (${Math.round(stats.ttft_p50_ms)} ms)` : `● p50 TTFT ${Math.round(stats.ttft_p50_ms)} ms`;
  const extras = [
    ['Understanding', stats.understanding ? `${stats.understanding.mode === 'llm' ? 'LLM' : 'Rules'} (${stats.understanding.llm} LLM, ${stats.understanding.timeout} timeouts)` : '—'],
    ['Failovers', `${stats.failovers ?? 0}`],
    ['Partial answers', `${stats.partial_turns ?? 0}`],
  ];

  return <section className="border-t hairline pt-8">
    <div className="flex items-end justify-between border-b hairline pb-4"><div><p className="editorial-mono text-[10px] uppercase tracking-[.16em] text-[#696862]">Technical notes</p><h2 className="editorial-serif mt-2 text-3xl">The response, measured quietly.</h2></div><span className="editorial-mono text-[10px] uppercase tracking-[.13em] text-[#20201e] dark:text-[#f1f0ea] font-semibold">{badge}</span></div>
    <dl className="grid grid-cols-2 border-b hairline md:grid-cols-4">{measures.map(([term, value]) => <div key={term} className="border-r hairline px-4 py-6 first:pl-0 last:border-0"><dt className="editorial-mono text-[9px] uppercase tracking-[.12em] text-[#77756e]">{term}</dt><dd className="mt-2 editorial-serif text-3xl">{value}</dd></div>)}</dl>
    <p className="mt-3 text-xs text-[#77756e]">TTFT is measured on the backend, from receiving the request to sending the first spoken token back to Agora. It does not include speech recognition, end-of-speech detection or speech synthesis.</p>
    <div className="mt-7 grid gap-8 md:grid-cols-3">
      <div><p className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#696862]">Model distribution</p>{Object.entries(stats.model_breakdown || {}).map(([name, count]) => <p key={name} className="flex justify-between border-b hairline py-3 text-sm"><span>{name.replace('_', ' ')}</span><span className="editorial-mono text-xs">{count} turns</span></p>)}</div>
      <div><p className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#696862]">Reliability</p>{extras.map(([name, value]) => <p key={name} className="flex justify-between gap-3 border-b hairline py-3 text-sm"><span>{name}</span><span className="editorial-mono text-right text-xs">{value}</span></p>)}</div>
      <div><p className="editorial-mono text-[10px] uppercase tracking-[.14em] text-[#696862]">Memory changes</p>{dealState.change_log?.length ? dealState.change_log.slice(-10).map((entry, i) => <p key={i} className="border-b hairline py-3 text-sm text-[#4c4b46]">{entry.description}</p>) : <p className="mt-4 text-sm italic text-[#77756e]">No changes have been recorded in this conversation.</p>}</div>
    </div>
  </section>;
};
