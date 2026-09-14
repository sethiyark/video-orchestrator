import React from "react";
import {
  AbsoluteFill,
  Audio,
  Composition,
  Img,
  Sequence,
  registerRoot,
  staticFile,
  useCurrentFrame,
} from "remotion";

import { COMPONENTS, FULL_FRAME } from "./components/index.mjs";
import { Title } from "./components/shared.jsx";
import { useFonts } from "./fonts.mjs";
import { Captions } from "./layout/Captions.jsx";
import { Frame } from "./layout/Frame.jsx";
import { Header } from "./layout/Header.jsx";
import { OPENER_FRAMES, Opener } from "./layout/Opener.jsx";
import { Rail } from "./layout/Rail.jsx";
import {
  OVERLAP,
  clamp,
  ease,
  handover,
  musicGain,
  pickTransition,
} from "./motion.mjs";
import { buildTheme } from "./theme.mjs";

// How a scene enters, as CSS, given the transition name and progress.
const entrance = (transition, enter) => {
  switch (transition) {
    case "slide":
      return { transform: `translateX(${(1 - enter) * 6}%)`, opacity: enter };
    case "wipe":
      return { clipPath: `inset(0 0 0 ${(1 - enter) * 100}%)` };
    case "chapter":
      return { clipPath: `inset(0 ${(1 - enter) * 100}% 0 0)` };
    default:
      return { opacity: enter };
  }
};

const Scene = ({ scene, chapter, index, total, theme, last }) => {
  const frame = useCurrentFrame();
  const frames = scene.frames;
  const Component = COMPONENTS[scene.component];
  if (!Component) throw new Error("Unsupported scene component");
  const accent = theme.accent(chapter.accent);
  const progress = clamp(frame / Math.max(1, frames - 1));
  const enterAmount = ease(frame / 22);
  const { enter, exit } = handover(frame, frames, last);
  const opensChapter = scene.scene_id === chapter.first_scene;
  const transition = pickTransition(chapter.index, index, opensChapter);
  const full = FULL_FRAME.has(scene.component);
  const opener = opensChapter && !full && frames > OPENER_FRAMES + 30;
  return (
    <AbsoluteFill
      style={{
        ...entrance(transition, enter),
        opacity: (entrance(transition, enter).opacity ?? 1) * (1 - exit),
        transform: `${entrance(transition, enter).transform || ""} scale(${1 - exit * 0.03})`,
      }}
    >
      <Frame plate={scene.plate} accent={accent} progress={progress} theme={theme} dim={full ? 0.3 : 0.55}>
        <div style={{ position: "relative", padding: "66px 140px", overflowWrap: "anywhere" }}>
          {!full && (
            <>
              <Header theme={theme} accent={accent} chapter={chapter} index={index} total={total} entrance={enterAmount} />
              <Title entrance={enterAmount}>{scene.props.title}</Title>
              <div style={{ height: 4, width: 90 + 110 * enterAmount, background: accent, marginBottom: 24 }} />
            </>
          )}
          <Component
            scene={scene}
            chapter={chapter}
            accent={accent}
            theme={theme}
            frame={frame}
            frames={frames}
            index={index}
            progress={progress}
          />
        </div>
        {opener && <Opener chapter={chapter} accent={accent} theme={theme} frame={frame} />}
      </Frame>
    </AbsoluteFill>
  );
};

// Brand intro before the first scene: logo or intro plate with a reveal.
const Intro = ({ theme, frames }) => {
  const frame = useCurrentFrame();
  const enter = ease(frame / 20);
  const leave = clamp((frame - frames) / OVERLAP);
  return (
    <AbsoluteFill style={{ background: theme.bg, opacity: 1 - leave, display: "grid", placeItems: "center", color: theme.text, fontFamily: theme.sans }}>
      {theme.intro ? (
        <Img src={staticFile(theme.intro)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1.1 - enter * 0.1})`, opacity: enter }} />
      ) : (
        <div style={{ textAlign: "center", opacity: enter, transform: `scale(${0.9 + enter * 0.1})` }}>
          {theme.logo && <Img src={staticFile(theme.logo)} style={{ height: 220, objectFit: "contain", marginBottom: 40 }} />}
          <div style={{ fontSize: 34, letterSpacing: 10, fontWeight: 700, color: theme.accent(0) }}>{theme.name}</div>
        </div>
      )}
    </AbsoluteFill>
  );
};

const Overlay = ({ scenes, chapters, words, captions, theme }) => {
  const frame = useCurrentFrame();
  const current = scenes.findIndex((s) => frame >= s.from && frame < s.from + s.frames);
  const chapter = current >= 0 ? chapters[scenes[current].chapter] : null;
  const accent = theme.accent(chapter ? chapter.accent : 0);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", fontFamily: theme.sans }}>
      {captions && current >= 0 && !FULL_FRAME.has(scenes[current].component) && (
        <Captions words={words} sceneIndex={current} frame={frame} accent={accent} theme={theme} />
      )}
      <Rail chapters={chapters} frame={frame} theme={theme} />
    </AbsoluteFill>
  );
};

const Video = ({ scenes, chapters, words, audio, music, brand, captions, introFrames, durationInFrames }) => {
  useFonts();
  const theme = buildTheme(brand);
  return (
    <AbsoluteFill style={{ background: theme.bg }}>
      {introFrames > 0 && (
        <Sequence from={0} durationInFrames={introFrames + OVERLAP}>
          <Intro theme={theme} frames={introFrames} />
        </Sequence>
      )}
      {scenes.map((scene, index) => (
        <Sequence
          key={scene.scene_id}
          from={scene.from}
          durationInFrames={scene.frames + (index === scenes.length - 1 ? 0 : OVERLAP)}
        >
          <Scene
            scene={scene}
            chapter={chapters[scene.chapter]}
            index={index}
            total={scenes.length}
            theme={theme}
            last={index === scenes.length - 1}
          />
        </Sequence>
      ))}
      <Overlay scenes={scenes} chapters={chapters} words={words} captions={captions} theme={theme} />
      <Sequence from={introFrames}>
        <Audio src={staticFile(audio)} />
      </Sequence>
      {music && (
        <Audio
          src={staticFile(music)}
          loop
          volume={(frame) => musicGain(words, frame, durationInFrames)}
        />
      )}
    </AbsoluteFill>
  );
};

registerRoot(() => (
  <Composition
    id="Explainer"
    component={Video}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={30}
    defaultProps={{
      scenes: [],
      chapters: [],
      words: [],
      audio: "narration.wav",
      music: null,
      brand: {},
      captions: true,
      introFrames: 0,
      durationInFrames: 30,
    }}
    calculateMetadata={({ props }) => ({ durationInFrames: props.durationInFrames })}
  />
));
