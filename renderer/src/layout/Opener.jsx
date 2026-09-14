import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

import { clamp, ease, easeInOut } from "../motion.mjs";

export const OPENER_FRAMES = 72;

// Chapter opener overlaying the first frames of a chapter whose first scene
// is not a ChapterTitle: number, title, tagline over the hero plate, then a
// wipe hands over to the scene.
export const Opener = ({ chapter, accent, theme, frame }) => {
  const enter = ease(frame / 14);
  const leave = easeInOut((frame - (OPENER_FRAMES - 18)) / 18);
  const visible = clamp(1 - leave);
  return (
    <AbsoluteFill
      style={{
        clipPath: `inset(0 ${leave * 100}% 0 0)`,
        opacity: frame < OPENER_FRAMES ? 1 : 0,
        background: theme.bg,
        fontFamily: theme.sans,
        color: theme.text,
      }}
    >
      {chapter.image && (
        <Img
          src={staticFile(chapter.image)}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${1.08 - enter * 0.06})`,
            filter: "brightness(0.55) saturate(1.1)",
          }}
        />
      )}
      <AbsoluteFill
        style={{
          background: `linear-gradient(90deg, ${theme.bg}f2 0%, ${theme.bg}a0 55%, transparent 100%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 300,
          opacity: enter * visible,
          transform: `translateX(${(1 - enter) * -40}px)`,
        }}
      >
        <div style={{ color: accent, fontSize: 26, letterSpacing: 8, fontWeight: 700 }}>
          CHAPTER {String(chapter.index + 1).padStart(2, "0")}
        </div>
        <div
          style={{
            fontSize: 96,
            fontWeight: 800,
            lineHeight: 1.05,
            margin: "22px 0 26px",
            maxWidth: 1200,
            letterSpacing: -1,
          }}
        >
          {chapter.title}
        </div>
        <div style={{ height: 6, width: 120 + 220 * enter, background: accent }} />
        {chapter.tagline && (
          <div style={{ fontSize: 36, color: theme.muted, marginTop: 30, maxWidth: 1100 }}>
            {chapter.tagline}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
