import React from "react";

import { typewriter } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

// Commands type out character by character; output lines appear when the
// command before them has finished typing.
export const Terminal = ({ scene, accent, theme, frame, frames }) => {
  const lines = scene.props.lines;
  const budget = frames * 0.65;
  const chars = lines.reduce((sum, l) => sum + (l.kind === "command" ? l.text.length : 4), 0);
  const perFrame = Math.max(0.6, chars / Math.max(1, budget));
  let cursor = 0;
  const rows = lines.map((line) => {
    const start = cursor;
    const length = line.kind === "command" ? line.text.length : 4;
    cursor += length / perFrame + 4;
    return { line, start, length };
  });
  const size = lines.length > 8 ? 24 : 30;
  return (
    <div style={panelStyle(theme, accent, { height: 600, overflow: "hidden", background: "#050b15ee" })}>
      <div style={{ padding: "16px 24px", borderBottom: `1px solid ${theme.line}`, color: theme.muted, fontSize: 20, fontFamily: theme.mono }}>
        ~ terminal
      </div>
      <div style={{ padding: "22px 30px", fontFamily: theme.mono, fontSize: size, lineHeight: 1.6 }}>
        {rows.map(({ line, start, length }, i) => {
          const shown = typewriter(frame, start, length, perFrame);
          if (shown <= 0) return null;
          const command = line.kind === "command";
          const text = command ? line.text.slice(0, shown) : line.text;
          const typing = command && shown < length;
          return (
            <div key={i} style={{ display: "flex", gap: 14, color: command ? theme.text : theme.muted }}>
              {command && <span style={{ color: accent, fontWeight: 600 }}>$</span>}
              <span style={{ whiteSpace: "pre-wrap" }}>
                {text}
                {typing && <span style={{ background: accent, marginLeft: 2 }}>&nbsp;</span>}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
