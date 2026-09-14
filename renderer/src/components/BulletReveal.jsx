import React from "react";

import { revealAt } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

export const BulletReveal = ({ scene, accent, theme, frame, frames }) => {
  const p = scene.props;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: p.bullets.length > 3 ? "1fr 1fr" : "1fr",
        gap: 22,
        paddingTop: 30,
      }}
    >
      {p.bullets.map((bullet, i) => {
        const amount = revealAt(frame, frames, i, p.bullets.length);
        return (
          <div
            key={i}
            style={panelStyle(theme, accent, {
              padding: "26px 32px",
              display: "flex",
              alignItems: "center",
              gap: 28,
              opacity: amount,
              transform: `translateX(${(1 - amount) * 45}px)`,
            })}
          >
            <div style={{ color: accent, fontSize: 38, fontWeight: 800, flexShrink: 0 }}>
              {String(i + 1).padStart(2, "0")}
            </div>
            <div style={{ fontSize: p.bullets.length > 3 ? 32 : 40, lineHeight: 1.35, fontWeight: 500 }}>
              {bullet}
            </div>
          </div>
        );
      })}
    </div>
  );
};
