import React from 'react';
import { AbsoluteFill, Img, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { T } from '../theme';
import { Backdrop, Chip, Rise, SceneFade } from '../ui';

export const Outro: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame: f - 3, fps, config: { damping: 15, stiffness: 110 } });
  const d = durationInFrames;

  return (
    <Backdrop>
      <SceneFade durationInFrames={durationInFrames} outF={20}>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', gap: 30 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 26, transform: `scale(${pop})` }}>
            <Img src={staticFile('cedar-mark.png')} style={{ width: 104, height: 104 }} />
            <div style={{ fontSize: 100, fontWeight: 800, letterSpacing: '-0.03em' }}>Cedar</div>
          </div>

          <Rise delay={16}>
            <div style={{ fontSize: 44, color: T.text2, fontWeight: 600 }}>
              Autonomous capital movement — with a built-in{' '}
              <span style={{ color: T.accent, fontWeight: 800 }}>“no.”</span>
            </div>
          </Rise>

          <Rise delay={Math.round(d * 0.42)}>
            <div style={{ display: 'flex', gap: 18, marginTop: 22 }}>
              <Chip color={T.accent} mono>
                trycedar.xyz
              </Chip>
              <Chip mono>github.com/mrfomoweb3/Cedar</Chip>
              <Chip mono>@trycedar</Chip>
            </div>
          </Rise>

          <Rise delay={Math.round(d * 0.6)}>
            <div style={{ fontSize: 28, color: T.text3, fontWeight: 600, letterSpacing: '0.06em' }}>
              MIT LICENSED · LIVE ON CASPER TESTNET · CASPER AGENTIC BUILDATHON 2026
            </div>
          </Rise>
        </AbsoluteFill>
      </SceneFade>
    </Backdrop>
  );
};
