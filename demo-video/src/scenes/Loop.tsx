import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { T } from '../theme';
import { Backdrop, Eyebrow, Rise, SceneFade } from '../ui';

// Fractions of the scene at which each step is narrated (matched to the VO).
const STEPS = [
  { k: 'OBSERVE', d: 'Live yields + on-chain allocations, read from contract storage', at: 0.05, c: T.accent },
  { k: 'VALIDATE', d: '9000% APY is a broken feed, not a jackpot → halt', at: 0.19, c: T.amber },
  { k: 'REASON', d: 'Llama 3.3 decides HOLD / REALLOCATE over validated data only', at: 0.35, c: T.blue },
  { k: 'RECHECK', d: 'Deterministic engine re-derives it. Disagree → refuse', at: 0.52, c: '#BC6A4A' },
  { k: 'GUARDRAILS', d: 'Cooldown · position cap · cost vs gain · anomaly breaker', at: 0.68, c: '#8E97C7' },
  { k: 'ACTUATE', d: 'Sign + submit the reallocation on Casper. Capture tx hash', at: 0.85, c: T.accent },
];

export const Loop: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const f = useCurrentFrame();
  const d = durationInFrames;

  return (
    <Backdrop>
      <SceneFade durationInFrames={durationInFrames}>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', padding: '90px 110px' }}>
          <Rise delay={4} style={{ textAlign: 'center', marginBottom: 60 }}>
            <Eyebrow>The autonomous loop</Eyebrow>
            <div style={{ fontSize: 64, fontWeight: 800, letterSpacing: '-0.02em' }}>
              Six steps. <span style={{ color: T.accent }}>No confirm button.</span>
            </div>
          </Rise>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 26, width: '100%' }}>
            {STEPS.map((s, i) => {
              const start = Math.round(d * s.at);
              // narration highlight: bright while its line is being spoken
              const next = i < 5 ? Math.round(d * STEPS[i + 1].at) : d - 20;
              const active = interpolate(f, [start, start + 8, next, next + 10], [0, 1, 1, 0.25], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              });
              return (
                <Rise key={s.k} delay={start} dist={36}>
                  <div
                    style={{
                      background: T.elevated,
                      borderRadius: 20,
                      border: `2px solid ${active > 0.6 ? s.c : T.border}`,
                      padding: '30px 34px',
                      minHeight: 190,
                      boxShadow: active > 0.6 ? `0 0 60px ${s.c}33` : '0 14px 40px rgba(0,0,0,0.4)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
                      <span style={{ fontSize: 28, fontWeight: 800, color: s.c, fontFamily: T.mono }}>
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <span style={{ fontSize: 40, fontWeight: 800, letterSpacing: '0.02em' }}>{s.k}</span>
                    </div>
                    <div style={{ fontSize: 29, color: T.text2, marginTop: 14, lineHeight: 1.4 }}>{s.d}</div>
                  </div>
                </Rise>
              );
            })}
          </div>

          <Rise delay={Math.round(d * 0.9)} style={{ marginTop: 54 }}>
            <div
              style={{
                border: `2px dashed ${T.accent}`,
                background: T.accentDim,
                borderRadius: 16,
                padding: '20px 54px',
                fontSize: 33,
                fontWeight: 700,
              }}
            >
              LOG — every cycle recorded, <span style={{ color: T.accent }}>action or refusal</span>
            </div>
          </Rise>
        </AbsoluteFill>
      </SceneFade>
    </Backdrop>
  );
};
