import React from "react";

import { ease } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

export const Callout = ({ scene, accent, theme, frame }) => {
  const p = scene.props;
  const enter = ease(frame / 20);
  return (
    <div style={{ display: "flex", justifyContent: "center", paddingTop: 30 }}>
      <div
        style={panelStyle(theme, accent, {
          maxWidth: 1400,
          padding: "60px 80px 50px",
          position: "relative",
          opacity: enter,
          transform: `scale(${0.96 + enter * 0.04})`,
        })}
      >
        <div style={{ position: "absolute", left: 40, top: -30, fontSize: 160, color: accent, fontWeight: 800, lineHeight: 1, opacity: 0.85 }}>
          “
        </div>
        <div style={{ fontSize: p.quote.length > 160 ? 40 : 50, lineHeight: 1.4, fontWeight: 600, fontStyle: "italic" }}>
          {p.quote}
        </div>
        <div style={{ marginTop: 30, display: "flex", alignItems: "center", gap: 16, color: theme.muted, fontSize: 24, letterSpacing: 2 }}>
          <div style={{ width: 40 + 60 * enter, height: 3, background: accent }} />
          VERIFIED SOURCE · {p.claim_id.toUpperCase()}
        </div>
      </div>
    </div>
  );
};
