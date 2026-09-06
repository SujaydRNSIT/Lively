import React, { useEffect, useRef, useState, useCallback } from 'react';

export type AgentExpression = 'idle' | 'listening' | 'thinking' | 'speaking' | 'happy' | 'empathetic' | 'surprised' | 'error';

/* ──────────────────────────────────────────────────────────────
   Eye shape map: different pupil sizes per expression
────────────────────────────────────────────────────────────── */
const EYES: Record<AgentExpression, { w: number; h: number; y: number; slash?: boolean }> = {
  idle:       { w: 26, h: 30,  y: 120 },
  listening:  { w: 26, h: 34,  y: 118 },
  thinking:   { w: 26, h: 14,  y: 128 },
  speaking:   { w: 26, h: 30,  y: 120 },
  happy:      { w: 26, h: 30,  y: 120 },
  empathetic: { w: 24, h: 26,  y: 122 },
  surprised:  { w: 36, h: 40,  y: 104 },
  error:      { w: 30, h:  8,  y: 128, slash: true },
};

const brows: Partial<Record<AgentExpression, Array<[number, number, number]>>> = {
  empathetic: [[123, 104, 8], [177, 104, -8]],
  surprised:  [[123, 88,  0], [177, 88,   0]],
};

/* ──────────────────────────────────────────────────────────────
   Mouth variants
────────────────────────────────────────────────────────────── */
function Mouth({ expression, jawOpen }: { expression: AgentExpression; jawOpen: number }) {
  if (expression === 'thinking')
    return <>{[138, 150, 162].map((x, i) => (
      <circle className="agent-face-dot" key={x} cx={x} cy="192" r="4"
        style={{ animationDelay: `${i * 0.15}s` }} />
    ))}</>;

  if (expression === 'surprised')
    return <rect x="138" y="182" width="24" height="24" rx="6" />;

  if (expression === 'happy')
    return <>
      <rect x="78"  y="178" width="16" height="16" />
      <rect x="94"  y="194" width="16" height="16" />
      <rect x="110" y="210" width="80" height="16" />
      <rect x="190" y="194" width="16" height="16" />
      <rect x="206" y="178" width="16" height="16" />
    </>;

  if (expression === 'empathetic' || expression === 'error') {
    const offsets = expression === 'empathetic' ? [4, 1, 0, 1, 4] : [0, 10, 0, 10, 0];
    return <>{[-36, -18, 0, 18, 36].map((dx, i) => (
      <rect key={dx} x={150 + dx - 7} y={192 + offsets[i]} width="14" height="10" rx="2"
        className={expression === 'error' ? 'agent-face-accent' : ''} />
    ))}</>;
  }

  /* idle / listening / speaking */
  const isListening = expression === 'listening';
  const isSpeaking  = expression === 'speaking';
  const openExtra   = isSpeaking ? jawOpen * 18 : 0; // dynamic jaw

  return (
    <rect
      className={isSpeaking ? 'agent-face-talking' : ''}
      x={150 - (isListening ? 25 : isSpeaking ? 30 : 45)}
      y={isListening ? 196 : isSpeaking ? 186 : 192}
      width={isListening ? 50 : isSpeaking ? 60 : 90}
      height={isListening ? 8 : isSpeaking ? 14 + openExtra : 14}
      rx={isListening ? 4 : isSpeaking ? 3 : 2}
    />
  );
}

/* ──────────────────────────────────────────────────────────────
   Main Component
────────────────────────────────────────────────────────────── */
interface AgentExpressionProps {
  expression: AgentExpression;
  label: string;
}

export const AgentExpression: React.FC<AgentExpressionProps> = ({ expression, label }) => {
  // --- Eye gaze wander (idle / listening only) ---
  const [gazeX, setGazeX] = useState(0);
  const [gazeY, setGazeY] = useState(0);
  const gazeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- Jaw bounce (speaking) ---
  const [jawOpen, setJawOpen] = useState(0);
  const jawFrame = useRef<number | null>(null);
  const jawPhase = useRef(0);

  // --- Head tilt / bob ---
  const [headTilt, setHeadTilt] = useState(0);
  const [headBobY, setHeadBobY] = useState(0);

  // --- Blink state ---
  const [blink, setBlink] = useState(false);
  const blinkTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Gaze wander when idle or listening ──────────────────────
  const scheduleGaze = useCallback(() => {
    const isWandering = expression === 'idle' || expression === 'listening';
    if (!isWandering) { setGazeX(0); setGazeY(0); return; }
    gazeTimer.current = setTimeout(() => {
      const angle = Math.random() * Math.PI * 2;
      const radius = expression === 'listening' ? 5 : 9;
      setGazeX(Math.cos(angle) * radius);
      setGazeY(Math.sin(angle) * radius * 0.6);
      scheduleGaze();
    }, 900 + Math.random() * 2000);
  }, [expression]);

  useEffect(() => {
    scheduleGaze();
    return () => { if (gazeTimer.current) clearTimeout(gazeTimer.current); };
  }, [scheduleGaze]);

  // ── Jaw animation when speaking ─────────────────────────────
  useEffect(() => {
    if (expression !== 'speaking') {
      setJawOpen(0);
      if (jawFrame.current) cancelAnimationFrame(jawFrame.current);
      return;
    }
    const animate = () => {
      jawPhase.current += 0.12;
      setJawOpen(Math.abs(Math.sin(jawPhase.current)));
      jawFrame.current = requestAnimationFrame(animate);
    };
    jawFrame.current = requestAnimationFrame(animate);
    return () => { if (jawFrame.current) cancelAnimationFrame(jawFrame.current); };
  }, [expression]);

  // ── Head movement per expression ────────────────────────────
  useEffect(() => {
    if (expression === 'empathetic') { setHeadTilt(-5); setHeadBobY(0); }
    else if (expression === 'thinking') { setHeadTilt(6); setHeadBobY(2); }
    else if (expression === 'surprised') { setHeadTilt(0); setHeadBobY(-6); }
    else if (expression === 'happy') { setHeadTilt(3); setHeadBobY(-2); }
    else if (expression === 'listening') { setHeadTilt(-2); setHeadBobY(0); }
    else { setHeadTilt(0); setHeadBobY(0); }
  }, [expression]);

  // ── Blink ────────────────────────────────────────────────────
  const scheduleBlink = useCallback(() => {
    blinkTimer.current = setTimeout(() => {
      setBlink(true);
      setTimeout(() => {
        setBlink(false);
        scheduleBlink();
      }, 120);
    }, 2800 + Math.random() * 3200);
  }, []);

  useEffect(() => {
    scheduleBlink();
    return () => { if (blinkTimer.current) clearTimeout(blinkTimer.current); };
  }, [scheduleBlink]);

  // ── Render ───────────────────────────────────────────────────
  const eye = EYES[expression];

  const eyeScaleY = blink
    ? 0.06
    : expression === 'thinking' ? 0.55
    : 1;

  const stageClasses = [
    'agent-face-stage',
    `st-${expression}`,
    expression === 'speaking' ? 'is-speaking' : '',
    expression === 'listening' ? 'is-listening' : '',
  ].filter(Boolean).join(' ');

  return (
    <div
      className={stageClasses}
      role="img"
      aria-label={`Lively is ${label.toLowerCase()}`}
    >

      <svg viewBox="60 65 180 180" aria-hidden="true">
        <g
          className="agent-face-root"
          style={{
            transform: `rotate(${headTilt}deg) translateY(${headBobY}px)`,
            transition: 'transform 0.55s cubic-bezier(.25,.75,.25,1)',
          }}
        >
          {/* Eyebrows */}
          {brows[expression]?.map(([cx, y, rot], i) => (
            <rect
              key={i}
              className="agent-face-brow"
              x={cx - 11} y={y} width="22" height="6" rx="2"
              style={{
                transform: `rotate(${rot}deg)`,
                transformBox: 'fill-box',
                transformOrigin: 'center',
              }}
            />
          ))}

          {/* Eyes */}
          {[123, 177].map((cx, idx) => (
            <rect
              key={cx}
              className="agent-face-eye"
              x={cx - eye.w / 2 + (idx === 0 ? gazeX : gazeX)}
              y={eye.y + gazeY}
              width={eye.w}
              height={eye.h}
              rx={expression === 'surprised' ? 4 : 0}
              style={{
                transform: `scaleY(${eye.slash ? 1 : eyeScaleY})`,
                rotate: eye.slash ? '45deg' : undefined,
                transformBox: 'fill-box',
                transformOrigin: 'center',
                transition: blink
                  ? 'transform 0.06s ease'
                  : 'transform 0.18s ease, x 0.45s ease, y 0.45s ease',
              }}
            />
          ))}

          {/* Mouth */}
          <g className="agent-face-mouth">
            <Mouth expression={expression} jawOpen={jawOpen} />
          </g>
        </g>
      </svg>
    </div>
  );
};
