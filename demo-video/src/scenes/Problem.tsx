import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { T } from '../theme';
import { Backdrop, Card, Eyebrow, Rise, SceneFade } from '../ui';

const Box: React.FC<{ label: string; color?: string }> = ({ label, color = T.text }) => (
  <div
    style={{
      padding: '26px 44px',
      borderRadius: 16,
      border: `2px solid ${T.border}`,
      background: T.elevated,
      fontSize: 40,
      fontWeight: 700,
      color,
    }}
  >
    {label}
  </div>
);

const Arrow: React.FC<{ color?: string }> = ({ color = T.text3 }) => (
  <div style={{ fontSize: 46, color, fontWeight: 700 }}>→</div>
);

export const Problem: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const f = useCurrentFrame();
  const d = durationInFrames;
  // the "reckless" wiring flashes red around 35% of the narration
  const danger = interpolate(f, [d * 0.3, d * 0.36], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <Backdrop>
      <SceneFade durationInFrames={durationInFrames}>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', gap: 56, padding: 120 }}>
          <Rise delay={4} style={{ textAlign: 'center' }}>
            <Eyebrow>The problem</Eyebrow>
            <div style={{ fontSize: 62, fontWeight: 800, letterSpacing: '-0.02em', lineHeight: 1.15 }}>
              Most agent demos wire a model
              <br />
              straight to the money.
            </div>
          </Rise>

          <Rise delay={Math.round(d * 0.24)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 26 }}>
              <Box label="LLM" />
              <Arrow color={danger > 0.5 ? T.red : T.text3} />
              <Box label="YOUR CAPITAL" color={danger > 0.5 ? T.red : T.text} />
              <div
                style={{
                  marginLeft: 18,
                  fontSize: 34,
                  fontWeight: 700,
                  color: T.red,
                  opacity: danger,
                }}
              >
                ⚠ one hallucination from a loss
              </div>
            </div>
          </Rise>

          <Rise delay={Math.round(d * 0.55)}>
            <Card accent={T.accent} style={{ maxWidth: 1250 }}>
              <div style={{ fontSize: 46, fontWeight: 700, lineHeight: 1.35, textAlign: 'center' }}>
                “An autonomous agent that touches capital is only as good as
                <br />
                the things it <span style={{ color: T.accent }}>refuses</span> to do.”
              </div>
            </Card>
          </Rise>

          <Rise delay={Math.round(d * 0.78)}>
            <div style={{ fontSize: 36, color: T.text2, fontWeight: 600 }}>
              Cedar’s answer: put the model inside a pipeline —{' '}
              <span style={{ color: T.text }}>where every other link can veto it.</span>
            </div>
          </Rise>
        </AbsoluteFill>
      </SceneFade>
    </Backdrop>
  );
};
