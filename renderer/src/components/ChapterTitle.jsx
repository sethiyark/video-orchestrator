import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

import { ease } from "../motion.mjs";

// Full-frame chapter hook: the hero image unblurred with a slow push-in.
export const ChapterTitle = ({ scene, chapter, accent, theme, frame, progress }) => {
  const p = scene.props;
  const enter = ease(frame / 18);
  const image = scene.image || (chapter && chapter.image);
  return (
    <AbsoluteFill style={{ width: 1920, height: 1080 }}>
      {image && (
        <Img
          src={staticFile(image)}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${1.06 + progress * 0.06})`,
            filter: "brightness(0.6) saturate(1.1)",
          }}
        />
      )}
      <AbsoluteFill
        style={{
          background: `linear-gradient(90deg, ${theme.bg}f4 0%, ${theme.bg}99 50%, ${theme.bg}22 100%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 330,
          maxWidth: 1250,
          opacity: enter,
          transform: `translateY(${(1 - enter) * 30}px)`,
        }}
      >
        {chapter && (
          <div style={{ color: accent, fontSize: 26, letterSpacing: 8, fontWeight: 700 }}>
            CHAPTER {String(chapter.index + 1).padStart(2, "0")}
          </div>
        )}
        <div style={{ fontSize: p.title.length > 40 ? 84 : 108, fontWeight: 800, lineHeight: 1.02, margin: "22px 0 28px", letterSpacing: -1.5 }}>
          {p.title}
        </div>
        <div style={{ height: 6, width: 100 + 260 * enter, background: accent }} />
        {p.subtitle && (
          <div style={{ fontSize: 38, color: theme.muted, marginTop: 30, fontWeight: 500 }}>{p.subtitle}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};
