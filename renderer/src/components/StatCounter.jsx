import React from "react";

import { counter, revealAt } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

// Animates the leading number of a value like "1.2M", "40%", "$3"; anything
// without a parseable number fades in unchanged.
const split = (value) => {
  const match = value.match(/^([^\d-]*)(-?\d+(?:[.,]\d+)?)(.*)$/);
  if (!match) return null;
  const decimals = (match[2].split(/[.,]/)[1] || "").length;
  return { prefix: match[1], number: parseFloat(match[2].replace(",", ".")), suffix: match[3], decimals };
};

export const StatCounter = ({ scene, accent, theme, frame, frames }) => {
  const stats = scene.props.stats;
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${stats.length}, 1fr)`, gap: 28, paddingTop: 20 }}>
      {stats.map((stat, i) => {
        const amount = revealAt(frame, frames, i, stats.length);
        const parts = split(stat.value);
        const shown = parts
          ? `${parts.prefix}${counter(frame, frames, parts.number).toFixed(parts.decimals)}${parts.suffix}`
          : stat.value;
        return (
          <div
            key={i}
            style={panelStyle(theme, accent, {
              padding: "48px 30px",
              textAlign: "center",
              opacity: amount,
              transform: `translateY(${(1 - amount) * 30}px)`,
              borderBottom: `5px solid ${theme.accent(i + 1)}`,
            })}
          >
            <div style={{ fontSize: stats.length > 2 ? 84 : 120, fontWeight: 800, color: theme.accent(i + 1), letterSpacing: -2, lineHeight: 1 }}>
              {shown}
            </div>
            <div style={{ fontSize: 28, color: theme.muted, marginTop: 24, fontWeight: 500 }}>{stat.label}</div>
          </div>
        );
      })}
    </div>
  );
};
