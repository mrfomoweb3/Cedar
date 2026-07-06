import React from 'react';
import { AbsoluteFill } from 'remotion';
import { T } from '../theme';
import { Backdrop, Card, Chip, Eyebrow, Rise, SceneFade } from '../ui';

export const Safety: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const d = durationInFrames;
  return (
    <Backdrop>
      <SceneFade durationInFrames={durationInFrames}>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', padding: '90px 130px', gap: 44 }}>
          <Rise delay={4} style={{ textAlign: 'center' }}>
            <Eyebrow>Defense in depth</Eyebrow>
            <div style={{ fontSize: 64, fontWeight: 800, letterSpacing: '-0.02em' }}>
              The safety isn’t a prompt. <span style={{ color: T.accent }}>It’s code.</span>
            </div>
          </Rise>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 26, width: '100%' }}>
            <Rise delay={Math.round(d * 0.18)}>
              <Card accent={T.accent} style={{ minHeight: 210 }}>
                <div style={{ fontSize: 38, fontWeight: 800 }}>Fabrication check</div>
                <div style={{ fontSize: 30, color: T.text2, marginTop: 12, lineHeight: 1.45 }}>
                  Every figure the model cites is matched against the validated snapshot.
                  Invent a number → the cycle is <b style={{ color: T.text }}>force-HELD</b>.
                </div>
              </Card>
            </Rise>
            <Rise delay={Math.round(d * 0.42)}>
              <Card accent={T.amber} style={{ minHeight: 210 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
                  <div style={{ fontSize: 38, fontWeight: 800 }}>Honest provenance</div>
                  <Chip color={T.amber}>single-source · UNVERIFIED</Chip>
                </div>
                <div style={{ fontSize: 30, color: T.text2, marginTop: 12, lineHeight: 1.45 }}>
                  Uncorroborated data is flagged, surfaced in the trace —{' '}
                  <b style={{ color: T.text }}>never silently trusted</b>.
                </div>
              </Card>
            </Rise>
          </div>

          <Rise delay={Math.round(d * 0.62)} style={{ width: '100%' }}>
            <Card style={{ borderLeft: `6px solid ${T.red}` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 14 }}>
                <span
                  style={{
                    background: `${T.red}22`,
                    color: T.red,
                    borderRadius: 999,
                    padding: '8px 24px',
                    fontSize: 27,
                    fontWeight: 800,
                  }}
                >
                  BLOCKED
                </span>
                <span style={{ fontSize: 32, fontWeight: 700 }}>Guardrail Triggered — cost_check</span>
              </div>
              <div style={{ fontFamily: T.mono, fontSize: 28, color: T.text2, lineHeight: 1.5 }}>
                expected gain 1.76 CSPR over 30d &le; cost 5.25 CSPR (gas 5.0 + slippage) → refused, logged
              </div>
            </Card>
          </Rise>
        </AbsoluteFill>
      </SceneFade>
    </Backdrop>
  );
};
