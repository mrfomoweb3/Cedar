import React from 'react';
import { AbsoluteFill, Img, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { T } from '../theme';
import { Backdrop, Chip, Rise, SceneFade } from '../ui';

export const Intro: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame: f - 4, fps, config: { damping: 14, stiffness: 120, mass: 0.8 } });

  return (
    <Backdrop>
      <SceneFade durationInFrames={durationInFrames}>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', gap: 34 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 30, transform: `scale(${pop})` }}>
            <Img src={staticFile('cedar-mark.png')} style={{ width: 128, height: 128 }} />
            <div style={{ fontSize: 120, fontWeight: 800, letterSpacing: '-0.03em' }}>Cedar</div>
          </div>

          <Rise delay={22}>
            <div style={{ fontSize: 50, fontWeight: 600, color: T.text2, textAlign: 'center', lineHeight: 1.25 }}>
              Moves <span style={{ color: T.accent, fontWeight: 800 }}>real capital</span> — under a mandate
              <br />
              it can <span style={{ color: T.accent, fontWeight: 800 }}>prove</span> it obeyed.
            </div>
          </Rise>

          <Rise delay={70}>
            <div style={{ display: 'flex', gap: 18, marginTop: 26 }}>
              <Chip color={T.accent}>● REAL CSPR CUSTODY</Chip>
              <Chip>PLAIN-ENGLISH MANDATES</Chip>
              <Chip>SELF-SIGNING</Chip>
              <Chip>NO HUMAN IN THE LOOP</Chip>
            </div>
          </Rise>
        </AbsoluteFill>
      </SceneFade>
    </Backdrop>
  );
};
