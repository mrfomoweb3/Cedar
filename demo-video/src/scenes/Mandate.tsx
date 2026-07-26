import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { T } from '../theme';
import { Backdrop, Card, Chip, Eyebrow, Rise, SceneFade } from '../ui';

export const Mandate: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const f = useCurrentFrame();
  const d = durationInFrames;
  // the "500 -> 200" clamp animates as the narration reaches the envelope point
  const clamp = interpolate(f, [d * 0.62, d * 0.72], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <Backdrop>
      <SceneFade durationInFrames={durationInFrames}>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', padding: '80px 120px', gap: 40 }}>
          <Rise delay={4} style={{ textAlign: 'center' }}>
            <Eyebrow>New · Plain-English mandates</Eyebrow>
            <div style={{ fontSize: 62, fontWeight: 800, letterSpacing: '-0.02em', lineHeight: 1.12 }}>
              Tell your capital what to do <span style={{ color: T.accent }}>in a sentence.</span>
            </div>
          </Rise>

          {/* the mandate itself, typed as an instruction */}
          <Rise delay={Math.round(d * 0.16)}>
            <Card style={{ maxWidth: 1200, borderLeft: `6px solid ${T.accent}` }}>
              <div style={{ fontSize: 22, color: T.text3, fontWeight: 600, letterSpacing: '0.05em', marginBottom: 12 }}>
                YOUR MANDATE
              </div>
              <div style={{ fontSize: 38, fontWeight: 600, lineHeight: 1.4, color: T.text }}>
                “Stay conservative. Keep at least <span style={{ color: T.accent }}>20%</span> in the stable
                pool, and never move more than <span style={{ color: T.accent }}>20%</span> at once.”
              </div>
            </Card>
          </Rise>

          {/* proposes / disposes */}
          <Rise delay={Math.round(d * 0.5)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 22 }}>
              <Card style={{ minWidth: 360 }}>
                <div style={{ fontSize: 24, color: T.text3, fontWeight: 600 }}>🧠 The model proposes</div>
                <div style={{ fontSize: 40, fontWeight: 800, marginTop: 10 }}>
                  move <span style={{ color: T.red, textDecoration: clamp > 0.5 ? 'line-through' : 'none' }}>500</span>
                </div>
              </Card>
              <div style={{ fontSize: 44, color: T.text3 }}>→</div>
              <Card accent={T.accent} style={{ minWidth: 360, boxShadow: clamp > 0.5 ? `0 0 60px ${T.accent}44` : undefined }}>
                <div style={{ fontSize: 24, color: T.text3, fontWeight: 600 }}>🛡️ The envelope disposes</div>
                <div style={{ fontSize: 40, fontWeight: 800, marginTop: 10, color: T.accent, opacity: clamp }}>
                  held to 200
                </div>
              </Card>
            </div>
          </Rise>

          <Rise delay={Math.round(d * 0.82)}>
            <div style={{ display: 'flex', gap: 14 }}>
              <Chip>deterministic recheck = safety bounds, not the exact move</Chip>
              <Chip color={T.accent}>the LLM finally earns its seat</Chip>
            </div>
          </Rise>
        </AbsoluteFill>
      </SceneFade>
    </Backdrop>
  );
};
