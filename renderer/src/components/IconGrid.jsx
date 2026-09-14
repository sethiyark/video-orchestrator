import React from "react";

import { Icon } from "../icons.jsx";
import { revealAt } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

export const IconGrid = ({ scene, accent, theme, frame, frames }) => {
  const items = scene.props.items;
  const columns = items.length <= 3 ? items.length : 3;
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: 26, paddingTop: 16 }}>
      {items.map((item, i) => {
        const amount = revealAt(frame, frames, i, items.length);
        const tint = theme.accent(i);
        return (
          <div
            key={i}
            style={panelStyle(theme, accent, {
              padding: items.length > 3 ? "30px 24px" : "48px 24px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 22,
              opacity: amount,
              transform: `scale(${0.85 + amount * 0.15})`,
            })}
          >
            <div style={{ width: 120, height: 120, borderRadius: 60, background: `${tint}1f`, display: "grid", placeItems: "center" }}>
              <Icon name={item.icon} size={64} color={tint} />
            </div>
            <div style={{ fontSize: 30, fontWeight: 600, textAlign: "center" }}>{item.label}</div>
          </div>
        );
      })}
    </div>
  );
};
