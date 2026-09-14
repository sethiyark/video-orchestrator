import React from "react";

import { panelStyle } from "./shared.jsx";

export const DefinitionCard = ({ scene, accent, theme, frame }) => {
  const p = scene.props;
  return (
    <div style={{ display: "flex", gap: 65, alignItems: "center", height: 570 }}>
      <div style={{ width: 280, height: 280, position: "relative", flexShrink: 0 }}>
        {[0, 1, 2].map((ring) => (
          <div
            key={ring}
            style={{
              position: "absolute",
              inset: ring * 32,
              border: `2px solid ${accent}`,
              opacity: 0.2 + ring * 0.18,
              borderRadius: ring === 1 ? 40 : "50%",
              transform: `rotate(${frame * (ring === 1 ? 0.18 : -0.1)}deg)`,
            }}
          />
        ))}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "grid",
            placeItems: "center",
            fontSize: 76,
            color: accent,
          }}
        >
          ↗
        </div>
      </div>
      <div
        style={panelStyle(theme, accent, {
          padding: "42px 48px",
          borderLeft: `5px solid ${accent}`,
          flex: 1,
        })}
      >
        <div style={{ color: accent, fontSize: 20, letterSpacing: 4, marginBottom: 24, fontWeight: 700 }}>
          THE CORE IDEA
        </div>
        <div style={{ fontSize: p.body.length > 300 ? 36 : 48, lineHeight: 1.45, fontWeight: 500 }}>
          {p.body}
        </div>
      </div>
    </div>
  );
};
