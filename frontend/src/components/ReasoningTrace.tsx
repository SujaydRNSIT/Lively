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
    key:        'heard' as const,
    icon:       Brain,
    label:      'Heard',
    dotBg:      'bg-[#f0efea] dark:bg-[#1a1d2c]',
    dotBorder:  'border-[#d7d5ce] dark:border-[#2e3346]',
    iconColor:  'text-[#696862] dark:text-[#a1a1aa]',
    labelColor: 'text-[#696862] dark:text-[#a1a1aa]',
    bg:         'bg-[#faf9f6] dark:bg-[#13151f]',
    border:     'border-[#e5e4de] dark:border-[#222533]',
  },
  {
    key:        'decided' as const,
    icon:       Route,
    label:      'Decision',
    dotBg:      'bg-[#f0efea] dark:bg-[#1a1d2c]',
    dotBorder:  'border-[#d7d5ce] dark:border-[#2e3346]',
    iconColor:  'text-[#696862] dark:text-[#a1a1aa]',
    labelColor: 'text-[#696862] dark:text-[#a1a1aa]',
    bg:         'bg-[#faf9f6] dark:bg-[#13151f]',
    border:     'border-[#e5e4de] dark:border-[#222533]',
  },
  {
    key:        'did' as const,
    icon:       Wrench,
    label:      'Actions',
    dotBg:      'bg-[#f0efea] dark:bg-[#1a1d2c]',
    dotBorder:  'border-[#d7d5ce] dark:border-[#2e3346]',
    iconColor:  'text-[#4c4b46] dark:text-[#c4c2ba]',
    labelColor: 'text-[#4c4b46] dark:text-[#c4c2ba]',
    bg:         'bg-[#faf9f6] dark:bg-[#13151f]',
    border:     'border-[#e5e4de] dark:border-[#222533]',
  },
  {
    key:        'result' as const,
    icon:       CheckCircle2,
    label:      'Result',
    dotBg:      'bg-[#eceae2] dark:bg-[#1f2231]',
    dotBorder:  'border-[#cfccc2] dark:border-[#353a4d]',
    iconColor:  'text-[#20201e] dark:text-[#f1f0ea]',
    labelColor: 'text-[#20201e] dark:text-[#f1f0ea]',
    bg:         'bg-[#f3f2ec] dark:bg-[#161824]',
    border:     'border-[#dcdad0] dark:border-[#2a2d3c]',
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
  dotBg: string;
  dotBorder: string;
  iconColor: string;
  labelColor: string;
  bg: string;
  border: string;
  content: string | string[];
  index: number;
  isLast: boolean;
}> = ({ icon: Icon, label, dotBg, dotBorder, iconColor, labelColor, bg, border, content, index, isLast }) => {
  const textStr  = Array.isArray(content) ? content.join(' · ') : content;
  const animated = useTypewriter(textStr, 14);

  return (
    <div className="flex gap-3">
      {/* Timeline dot and connector */}
      <div className="flex flex-col items-center gap-0 shrink-0">
        <div
          className={`flex items-center justify-center w-7 h-7 rounded-full shrink-0 shadow-sm border ${dotBg} ${dotBorder} ${iconColor}`}
        >
          <Icon size={13} />
        </div>
        {!isLast && (
          <div className="w-px flex-1 mt-1 mb-0 bg-[#d7d5ce] dark:bg-[#282c3c]" style={{ minHeight: 16 }} />
        )}
      </div>

      {/* Step content */}
      <div className={`flex-1 rounded-xl border px-3 py-2.5 mb-2 ${bg} ${border}`} style={{ minHeight: 44 }}>
        <p
          className={`text-[9.5px] uppercase tracking-[.16em] font-semibold mb-1 ${labelColor}`}
        >
          {label}
        </p>
        {Array.isArray(content) && content.length > 0 ? (
          <ul className="space-y-0.5">
            {content.map((item, i) => (
              <li key={i} className="text-[11px] text-[#20201e] dark:text-[#e8e6e1] leading-relaxed flex items-start gap-1.5">
                <span className="shrink-0 mt-1 text-[#8c8a82] dark:text-[#6b7280]">›</span>
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
      className={`rounded-2xl border hairline bg-white dark:bg-[#141416] shadow-sm overflow-hidden transition-all duration-300 ${flash ? 'ring-2 ring-neutral-900/30 dark:ring-white/30' : ''}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b hairline">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#20201e] dark:bg-[#e8e6e1] animate-pulse" />
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
                dotBg={cfg.dotBg}
                dotBorder={cfg.dotBorder}
                iconColor={cfg.iconColor}
                labelColor={cfg.labelColor}
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
