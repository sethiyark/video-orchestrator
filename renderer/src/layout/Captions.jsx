import React from "react";

import { captionAt } from "../motion.mjs";

// Karaoke captions from the aligned word timeline; the active word glows.
export const Captions = ({ words, sceneIndex, frame, accent, theme }) => {
  const caption = captionAt(words, sceneIndex, frame);
  if (!caption) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: 140,
        right: 140,
        bottom: 76,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          background: "#03070fcc",
          border: `1px solid ${theme.line}`,
          borderRadius: 14,
          padding: "12px 26px",
          fontSize: 30,
          fontWeight: 500,
          lineHeight: 1.3,
          maxWidth: 1500,
          textAlign: "center",
        }}
      >
        {caption.line.map((word, i) => {
          const active = word === caption.active;
          const past = word.from < caption.active.from;
          return (
            <span
              key={i}
              style={{
                color: active ? accent : past ? theme.text : theme.muted,
                fontWeight: active ? 700 : 500,
                marginRight: 9,
                textShadow: active ? `0 0 18px ${accent}80` : undefined,
              }}
            >
              {word.text}
            </span>
          );
        })}
      </div>
    </div>
  );
};
