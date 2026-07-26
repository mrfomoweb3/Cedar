import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { T } from '../theme';
import { Backdrop, Card, Chip, Eyebrow, Rise, SceneFade } from '../ui';

const FLOW = [
  { k: 'deposit', d: 'real CSPR in', c: T.accent, tx: 'd9be9302…dcf6' },
  { k: 'reallocate', d: 'agent moves it', c: T.blue, tx: 'a4536350…67c0' },
  { k: 'withdraw', d: 'real CSPR out', c: T.amber, tx: 'be652b91…cd28' },
];

export const Custody: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const f = useCurrentFrame();
  const d = durationInFrames;
  // the backing counter ticks up to 465 as the vault "fills"
  const backing = Math.round(interpolate(f, [d * 0.18, d * 0.42], [0, 465], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  }));

  return (
    <Backdrop>
      <SceneFade durationInFrames={durationInFrames}>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', padding: '70px 120px', gap: 34 }}>
          <Rise delay={4} style={{ textAlign: 'center' }}>
            <Eyebrow>New · Real on-chain custody</Eyebrow>
            <div style={{ fontSize: 62, fontWeight: 800, letterSpacing: '-0.02em' }}>
              Not a ledger of intent. <span style={{ color: T.accent }}>Real capital.</span>
            </div>
          </Rise>

          {/* the vault, holding real CSPR */}
          <Rise delay={Math.round(d * 0.14)}>
            <Card accent={T.accent} style={{ minWidth: 720, textAlign: 'center' }}>
              <div style={{ fontSize: 24, color: T.text3, fontWeight: 600, letterSpacing: '0.05em' }}>
                VAULTROUTER · REAL CSPR CUSTODIED ON-CHAIN
              </div>
              <div style={{ fontSize: 92, fontWeight: 800, color: T.accent, fontVariantNumeric: 'tabular-nums', marginTop: 6 }}>
                {backing} <span style={{ fontSize: 40, color: T.text2 }}>CSPR</span>
              </div>
              <div style={{ fontFamily: T.mono, fontSize: 24, color: T.text2 }}>
                invariant: backing == Σ earmarks · <span style={{ color: T.accent }}>true</span>
              </div>
            </Card>
          </Rise>

          {/* the three real, verifiable operations */}
          <div style={{ display: 'flex', gap: 20 }}>
            {FLOW.map((s, i) => (
              <Rise key={s.k} delay={Math.round(d * (0.5 + i * 0.1))}>
                <Card style={{ minWidth: 330, borderTop: `4px solid ${s.c}` }}>
                  <div style={{ fontSize: 30, fontWeight: 800, color: s.c }}>{s.k}</div>
                  <div style={{ fontSize: 24, color: T.text2, margin: '6px 0 12px' }}>{s.d}</div>
                  <div style={{ fontFamily: T.mono, fontSize: 21, color: T.accent }}>{s.tx} ↗</div>
                </Card>
              </Rise>
            ))}
          </div>

          <Rise delay={Math.round(d * 0.86)}>
            <Chip mono color={T.accent}>hash-afdbf6c3…5bc71d7c · Odra · Casper Testnet</Chip>
          </Rise>
        </AbsoluteFill>
      </SceneFade>
    </Backdrop>
  );
};
