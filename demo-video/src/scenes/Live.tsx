import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { T } from '../theme';
import { Backdrop, Rise, SceneFade } from '../ui';

export const Live: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const f = useCurrentFrame();
  const d = durationInFrames;
  // slow Ken Burns over the real dashboard
  const scale = interpolate(f, [0, d], [1.02, 1.14]);
  const ty = interpolate(f, [0, d], [0, -60]);

  return (
    <Backdrop>
      <SceneFade durationInFrames={durationInFrames}>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
          {/* framed screenshot of the real live dashboard */}
          <Rise delay={2} style={{ width: '86%' }}>
            <div
              style={{
                borderRadius: 26,
                border: `2px solid ${T.border}`,
                overflow: 'hidden',
                boxShadow: `0 40px 140px rgba(0,0,0,0.65), 0 0 90px ${T.accent}22`,
              }}
            >
              {/* browser chrome bar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 14,
                  background: T.surface,
                  borderBottom: `1.5px solid ${T.border}`,
                  padding: '16px 26px',
                }}
              >
                <span style={{ display: 'flex', gap: 9 }}>
                  {['#E06C5E', '#E0A458', '#56C07B'].map((c) => (
                    <span key={c} style={{ width: 16, height: 16, borderRadius: 99, background: c }} />
                  ))}
                </span>
                <span
                  style={{
                    marginLeft: 16,
                    background: T.elevated,
                    border: `1.5px solid ${T.border}`,
                    borderRadius: 10,
                    padding: '8px 26px',
                    fontFamily: T.mono,
                    fontSize: 24,
                    color: T.text2,
                  }}
                >
                  🔒 <span style={{ color: T.accent, fontWeight: 700 }}>trycedar.xyz</span>/app — live
                </span>
              </div>
              <div style={{ overflow: 'hidden', height: 760 }}>
                <Img
                  src={staticFile('shot-dashboard.png')}
                  style={{
                    width: '100%',
                    transform: `scale(${scale}) translateY(${ty}px)`,
                    transformOrigin: '50% 18%',
                  }}
                />
              </div>
            </div>
          </Rise>

          {/* narration-timed callouts */}
          <Rise delay={Math.round(d * 0.35)} style={{ position: 'absolute', bottom: 64, display: 'flex', gap: 18 }}>
            {['EXECUTED + tx hash', 'BLOCKED + guardrail name', 'plain-English reasoning', 'pause · policy · audit'].map(
              (t) => (
                <span
                  key={t}
                  style={{
                    background: T.elevated,
                    border: `1.5px solid ${T.border}`,
                    borderRadius: 999,
                    padding: '12px 28px',
                    fontSize: 27,
                    fontWeight: 700,
                  }}
                >
                  {t}
                </span>
              ),
            )}
          </Rise>
        </AbsoluteFill>
      </SceneFade>
    </Backdrop>
  );
};
