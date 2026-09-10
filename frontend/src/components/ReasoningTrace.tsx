import React, { useEffect, useRef, useState } from 'react';
import { Brain, Route, Wrench, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';

interface ReasoningStep {
  heard:     string;
  decided:   string;
  did:       string[];
  result:    string;
  sentiment: string;
  provider:  string;
}

interface ReasoningTraceProps {
  /** Latest reasoning step received from AGENT_REASONING WebSocket event */
  reasoning: ReasoningStep | null;
}

const STEP_CONFIG = [
  {
    key:   'heard'   as const,
    icon:  Brain,
    label: 'Heard',
    color: '#6166cf',
    bg:    'bg-indigo-50 dark:bg-indigo-950/30',
    border:'border-indigo-200/60 dark:border-indigo-800/40',
  },
  {
    key:   'decided' as const,
    icon:  Route,
    label: 'Decision',
    color: '#8b5cf6',
    bg:    'bg-violet-50 dark:bg-violet-950/30',
    border:'border-violet-200/60 dark:border-violet-800/40',
  },
  {
    key:   'did'     as const,
    icon:  Wrench,
    label: 'Actions',
    color: '#0ea5e9',
    bg:    'bg-sky-50 dark:bg-sky-950/30',
    border:'border-sky-200/60 dark:border-sky-800/40',
  },
  {
    key:   'result'  as const,
    icon:  CheckCircle2,
    label: 'Result',
    color: '#10b981',
    bg:    'bg-emerald-50 dark:bg-emerald-950/30',
    border:'border-emerald-200/60 dark:border-emerald-800/40',
  },
];

/** Typewriter hook: animates text character by character */
function useTypewriter(text: string, speed = 18): string {
  const [displayed, setDisplayed] = useState('');
  const raf = useRef<number | null>(null);
  const idx  = useRef(0);

  useEffect(() => {
    setDisplayed('');
    idx.current = 0;
    if (!text) return;

    const tick = () => {
      if (idx.current < text.length) {
        setDisplayed(text.slice(0, idx.current + 1));
        idx.current++;
        raf.current = window.setTimeout(tick, speed);
      }
    };
    raf.current = window.setTimeout(tick, speed);
    return () => { if (raf.current) clearTimeout(raf.current); };
  }, [text, speed]);

  return displayed;
}

const TraceStep: React.FC<{
  icon: React.FC<any>;
  label: string;
  color: string;
  bg: string;
  border: string;
  content: string | string[];
  index: number;
  isLast: boolean;
}> = ({ icon: Icon, label, color, bg, border, content, index, isLast }) => {
  const textStr  = Array.isArray(content) ? content.join(' · ') : content;
  const animated = useTypewriter(textStr, 14);

  return (
    <div className="flex gap-3">
      {/* Timeline dot and connector */}
      <div className="flex flex-col items-center gap-0 shrink-0">
        <div
          className="flex items-center justify-center w-7 h-7 rounded-full shrink-0 shadow-sm"
          style={{ background: color + '18', border: `1.5px solid ${color}40` }}
        >
          <Icon size={13} style={{ color }} />
        </div>
        {!isLast && (
          <div className="w-px flex-1 mt-1 mb-0" style={{ background: `${color}28`, minHeight: 16 }} />
        )}
      </div>

      {/* Step content */}
      <div className={`flex-1 rounded-xl border px-3 py-2.5 mb-2 ${bg} ${border}`} style={{ minHeight: 44 }}>
        <p
          className="text-[9.5px] uppercase tracking-[.16em] font-semibold mb-1"
          style={{ color }}
        >
          {label}
        </p>
        {Array.isArray(content) && content.length > 0 ? (
          <ul className="space-y-0.5">
            {content.map((item, i) => (
              <li key={i} className="text-[11px] text-[#20201e] dark:text-[#e8e6e1] leading-relaxed flex items-start gap-1.5">
                <span className="shrink-0 mt-1" style={{ color, opacity: 0.6 }}>›</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[11.5px] text-[#20201e] dark:text-[#e8e6e1] leading-relaxed">
            {animated || <span className="opacity-30 italic">—</span>}
          </p>
        )}
      </div>
    </div>
  );
};

export const ReasoningTrace: React.FC<ReasoningTraceProps> = ({ reasoning }) => {
  const [collapsed, setCollapsed] = useState(false);
  const prevResult = useRef('');
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (reasoning?.result && reasoning.result !== prevResult.current) {
      prevResult.current = reasoning.result;
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 1200);
      return () => clearTimeout(t);
    }
  }, [reasoning?.result]);

  return (
    <div
      className={`rounded-2xl border hairline bg-white dark:bg-[#0f1118] shadow-sm overflow-hidden transition-all duration-300 ${flash ? 'ring-2 ring-[#6166cf]/30' : ''}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b hairline">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#6166cf] animate-pulse" />
          <span className="text-[10px] editorial-mono uppercase tracking-[.18em] text-[#696862] dark:text-[#9aa0ad] font-semibold">
            Agent Decision Trace
          </span>
          {reasoning?.provider && (
            <span className="text-[9px] editorial-mono px-1.5 py-0.5 rounded bg-[#f0efea] dark:bg-[#1a1d2a] text-[#8c8a82] dark:text-[#6b7280]">
              {reasoning.provider.replace('groq:', '').replace('nvidia:', '')}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {reasoning?.sentiment && (
            <span className="text-[10px] text-[#696862] dark:text-[#9aa0ad]">{reasoning.sentiment}</span>
          )}
          <button
            onClick={() => setCollapsed(c => !c)}
            className="p-1 rounded hover:bg-[#f0efea] dark:hover:bg-[#1a1d2a] transition"
            aria-label={collapsed ? 'Expand trace' : 'Collapse trace'}
          >
            {collapsed
              ? <ChevronDown size={13} className="text-[#8c8a82]" />
              : <ChevronUp   size={13} className="text-[#8c8a82]" />}
          </button>
        </div>
      </div>

      {/* Steps */}
      {!collapsed && (
        <div className="px-4 pt-4 pb-3">
          {!reasoning ? (
            <div className="py-8 text-center">
              <Brain size={22} className="mx-auto text-[#c8c6c0] dark:text-[#3a3f52] mb-2" />
              <p className="text-xs text-[#a7a59d] dark:text-[#5a6175] italic">
                Waiting for the first buyer turn…
              </p>
            </div>
          ) : (
            STEP_CONFIG.map((cfg, i) => (
              <TraceStep
                key={cfg.key}
                icon={cfg.icon}
                label={cfg.label}
                color={cfg.color}
                bg={cfg.bg}
                border={cfg.border}
                content={reasoning[cfg.key] as string | string[]}
                index={i}
                isLast={i === STEP_CONFIG.length - 1}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
};
