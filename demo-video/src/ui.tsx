import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { T } from './theme';
import { loadFont } from '@remotion/google-fonts/Inter';

const { fontFamily } = loadFont('normal', { weights: ['400', '500', '600', '700', '800'] });
export const FONT = fontFamily;

/** Scene backdrop: brand-dark with a faint grid and a soft radial accent glow. */
export const Backdrop: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ background: T.bg, fontFamily: FONT, color: T.text }}>
    <AbsoluteFill
      style={{
        backgroundImage: `linear-gradient(${T.border}33 1px, transparent 1px),
                          linear-gradient(90deg, ${T.border}33 1px, transparent 1px)`,
        backgroundSize: '72px 72px',
        maskImage: 'radial-gradient(ellipse 90% 80% at 50% 40%, black 45%, transparent 100%)',
      }}
    />
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse 55% 45% at 50% 8%, ${T.accent}14, transparent 70%)`,
      }}
    />
    {children}
  </AbsoluteFill>
);

/** Fade the whole scene in over `inF` frames and out over the last `outF`. */
export const SceneFade: React.FC<{
  durationInFrames: number;
  children: React.ReactNode;
  inF?: number;
  outF?: number;
}> = ({ durationInFrames, children, inF = 10, outF = 12 }) => {
  const f = useCurrentFrame();
  const opacity =
    interpolate(f, [0, inF], [0, 1], { extrapolateRight: 'clamp' }) *
    interpolate(f, [durationInFrames - outF, durationInFrames - 1], [1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

/** Spring-in wrapper: fades + rises + settles, starting at `delay` frames. */
export const Rise: React.FC<{
  delay: number;
  children: React.ReactNode;
  dist?: number;
  style?: React.CSSProperties;
}> = ({ delay, children, dist = 28, style }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: f - delay, fps, config: { damping: 200, stiffness: 90 } });
  return (
    <div
      style={{
        opacity: s,
        transform: `translateY(${(1 - s) * dist}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Chip: React.FC<{ children: React.ReactNode; color?: string; mono?: boolean }> = ({
  children,
  color = T.text2,
  mono,
}) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 10,
      padding: '10px 22px',
      borderRadius: 999,
      border: `1.5px solid ${T.border}`,
      background: T.elevated,
      color,
      fontSize: 26,
      fontWeight: 600,
      letterSpacing: '0.04em',
      fontFamily: mono ? T.mono : undefined,
    }}
  >
    {children}
  </span>
);

export const Card: React.FC<{ children: React.ReactNode; style?: React.CSSProperties; accent?: string }> = ({
  children,
  style,
  accent,
}) => (
  <div
    style={{
      background: T.elevated,
      border: `1.5px solid ${T.border}`,
      borderLeft: accent ? `6px solid ${accent}` : `1.5px solid ${T.border}`,
      borderRadius: 20,
      padding: '34px 40px',
      boxShadow: '0 18px 60px rgba(0,0,0,0.45)',
      ...style,
    }}
  >
    {children}
  </div>
);

/** Section label like the app's eyebrows. */
export const Eyebrow: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      fontSize: 26,
      fontWeight: 700,
      letterSpacing: '0.18em',
      color: T.accent,
      textTransform: 'uppercase',
      marginBottom: 18,
    }}
  >
    {children}
  </div>
);
