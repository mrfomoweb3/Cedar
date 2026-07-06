import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { T } from '../theme';
import { Backdrop, Card, Chip, Eyebrow, Rise, SceneFade } from '../ui';

const CODE = [
  { t: 'pub fn reallocate(&mut self, from_pool: PoolId,', c: T.text },
  { t: '                  to_pool: PoolId, amount: U512) {', c: T.text },
  { t: '    self.assert_owner();          // only the agent’s key', c: T.accent },
  { t: '    if amount == U512::zero() { revert(ZeroAmount) }', c: T.text2 },
  { t: '    if bal < amount { revert(InsufficientAllocation) }', c: T.text2 },
  { t: '    …move · emit Reallocated…', c: T.text3 },
  { t: '}', c: T.text },
];

const HASH = '0b80e11e8bb6127930e259fde4767f9a2f7a7954e143cb49ef792c96b9194ac7';

export const Contract: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const f = useCurrentFrame();
  const d = durationInFrames;
  // tx hash "types in" as the narration reaches the proof (~62%)
  const typed = Math.floor(
    interpolate(f, [d * 0.62, d * 0.74], [0, HASH.length], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    }),
  );

  return (
    <Backdrop>
      <SceneFade durationInFrames={durationInFrames}>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', padding: '80px 120px', gap: 40 }}>
          <Rise delay={4} style={{ textAlign: 'center' }}>
            <Eyebrow>On-chain · Odra (Rust) · Casper Testnet</Eyebrow>
            <div style={{ fontSize: 62, fontWeight: 800, letterSpacing: '-0.02em' }}>
              VaultRouter — <span style={{ color: T.accent }}>owner-gated by the contract itself</span>
            </div>
          </Rise>

          <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 1fr', gap: 30, width: '100%' }}>
            <Rise delay={Math.round(d * 0.14)}>
              <Card style={{ padding: '30px 36px' }}>
                <div style={{ fontFamily: T.mono, fontSize: 27.5, lineHeight: 1.75 }}>
                  {CODE.map((l, i) => (
                    <div key={i} style={{ color: l.c, whiteSpace: 'pre' }}>
                      {l.t}
                    </div>
                  ))}
                </div>
              </Card>
              <div style={{ marginTop: 18, display: 'flex', gap: 14 }}>
                <Chip mono>hash-2e027302…ae7b298d</Chip>
                <Chip color={T.accent}>NotOwner → revert</Chip>
              </div>
            </Rise>

            <Rise delay={Math.round(d * 0.55)}>
              <Card accent={T.accent} style={{ minHeight: 330 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 18 }}>
                  <span
                    style={{
                      background: T.accentDim,
                      color: T.accent,
                      borderRadius: 999,
                      padding: '8px 24px',
                      fontSize: 27,
                      fontWeight: 800,
                    }}
                  >
                    EXECUTED ✓
                  </span>
                  <span style={{ fontSize: 32, fontWeight: 700 }}>Real deploy · testnet.cspr.live</span>
                </div>
                <div style={{ fontSize: 34, fontWeight: 700, marginBottom: 14 }}>
                  reallocate&nbsp;&nbsp;PoolA <span style={{ color: T.accent }}>→</span> PoolB&nbsp;&nbsp;400
                </div>
                <div
                  style={{
                    fontFamily: T.mono,
                    fontSize: 25,
                    color: T.accent,
                    wordBreak: 'break-all',
                    lineHeight: 1.55,
                    minHeight: 84,
                  }}
                >
                  {HASH.slice(0, typed)}
                  <span style={{ opacity: typed < HASH.length ? 1 : 0 }}>▌</span>
                </div>
                <div style={{ fontSize: 27, color: T.text2, marginTop: 10 }}>
                  error_message: <span style={{ color: T.accent, fontWeight: 700 }}>none</span> · cost 5 CSPR ·
                  signed autonomously
                </div>
              </Card>
            </Rise>
          </div>
        </AbsoluteFill>
      </SceneFade>
    </Backdrop>
  );
};
