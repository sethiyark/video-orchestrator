import React from "react";

import { ease, revealAt } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

export const Comparison = ({ scene, accent, theme, frame, frames }) => {
  const { left, right } = scene.props;
  const total = left.points.length + right.points.length;
  const column = (side, offset, tint) => (
    <div style={panelStyle(theme, accent, { flex: 1, padding: "28px 34px", borderTop: `4px solid ${tint}` })}>
      <div style={{ color: tint, fontSize: 24, letterSpacing: 4, fontWeight: 700, marginBottom: 22 }}>
        {side.label.toUpperCase()}
      </div>
      {side.points.map((point, i) => {
        const amount = revealAt(frame, frames, offset + i, total);
        return (
          <div key={i} style={{ display: "flex", gap: 18, marginBottom: 16, opacity: amount, transform: `translateY(${(1 - amount) * 16}px)` }}>
            <div style={{ color: tint, fontSize: 30, lineHeight: 1.3 }}>•</div>
            <div style={{ fontSize: 30, lineHeight: 1.3, fontWeight: 500 }}>{point}</div>
          </div>
        );
      })}
    </div>
  );
  const pop = ease(frame / 16);
  return (
    <div style={{ display: "flex", gap: 40, position: "relative", minHeight: 520 }}>
      {column(left, 0, accent)}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: 200,
          transform: `translate(-50%, 0) scale(${pop})`,
          width: 96,
          height: 96,
          borderRadius: 48,
          background: theme.bg,
          border: `3px solid ${theme.line}`,
          display: "grid",
          placeItems: "center",
          fontSize: 30,
          fontWeight: 800,
          color: theme.muted,
        }}
      >
        VS
      </div>
      {column(right, left.points.length, theme.accent(11))}
    </div>
  );
};
