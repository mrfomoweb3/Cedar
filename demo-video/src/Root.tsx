import React from 'react';
import { Audio, Composition, Sequence, staticFile } from 'remotion';
import manifest from './audio-manifest.json';
import { FPS, H, W } from './theme';
import { Contract } from './scenes/Contract';
import { Intro } from './scenes/Intro';
import { Live } from './scenes/Live';
import { Loop } from './scenes/Loop';
import { Outro } from './scenes/Outro';
import { Problem } from './scenes/Problem';
import { Safety } from './scenes/Safety';

const TAIL = 0.9; // seconds of breathing room after each narration

const ORDER: { id: keyof typeof manifest; C: React.FC<{ durationInFrames: number }> }[] = [
  { id: 'intro', C: Intro },
  { id: 'problem', C: Problem },
  { id: 'loop', C: Loop },
  { id: 'safety', C: Safety },
  { id: 'contract', C: Contract },
  { id: 'live', C: Live },
  { id: 'outro', C: Outro },
];

const frames = (id: keyof typeof manifest) => Math.ceil((manifest[id] + TAIL) * FPS);
const TOTAL = ORDER.reduce((a, s) => a + frames(s.id), 0);

const Video: React.FC = () => {
  let from = 0;
  return (
    <>
      {ORDER.map(({ id, C }) => {
        const dur = frames(id);
        const el = (
          <Sequence key={id} from={from} durationInFrames={dur} name={id}>
            <C durationInFrames={dur} />
            <Audio src={staticFile(`audio/${id}.mp3`)} />
          </Sequence>
        );
        from += dur;
        return el;
      })}
    </>
  );
};

export const Root: React.FC = () => (
  <Composition
    id="CedarDemo"
    component={Video}
    durationInFrames={TOTAL}
    fps={FPS}
    width={W}
    height={H}
  />
);
