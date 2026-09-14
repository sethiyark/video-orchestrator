import React from "react";

import { tokenize } from "../highlight.mjs";
import { revealAt } from "../motion.mjs";
import { panelStyle } from "./shared.jsx";

const COLORS = {
  keyword: "#c4b5fd",
  string: "#86efac",
  comment: "#6b7d95",
  number: "#fbbf24",
  punctuation: "#9fb0c8",
  plain: "#edf3fc",
};

export const CodeBlock = ({ scene, accent, theme, frame, frames }) => {
  const p = scene.props;
  const lines = p.code.replace(/\r/g, "").split("\n").slice(0, 40);
  const size = lines.length > 14 ? 22 : lines.length > 9 ? 27 : 31;
  const highlight = new Set(p.highlight_lines || []);
  return (
    <div style={panelStyle(theme, accent, { overflow: "hidden", height: 600, display: "flex", flexDirection: "column" })}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 24px", borderBottom: `1px solid ${theme.line}`, background: "#0b1526" }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
          <div key={c} style={{ width: 14, height: 14, borderRadius: 7, background: c }} />
        ))}
        <div style={{ marginLeft: 16, color: theme.muted, fontSize: 20, fontFamily: theme.mono }}>{p.language}</div>
      </div>
      <pre style={{ margin: 0, padding: "24px 28px", fontFamily: theme.mono, fontSize: size, lineHeight: 1.5, flex: 1, overflow: "hidden" }}>
        {lines.map((line, i) => {
          const amount = revealAt(frame, frames, i, lines.length);
          const hot = highlight.has(i + 1);
          return (
            <div
              key={i}
              style={{
                display: "flex",
                opacity: amount,
                transform: `translateX(${(1 - amount) * 24}px)`,
                background: hot ? `${accent}22` : "transparent",
                borderLeft: hot ? `4px solid ${accent}` : "4px solid transparent",
                paddingLeft: 12,
                marginLeft: -16,
              }}
            >
              <span style={{ width: 52, color: "#4b5b73", userSelect: "none", flexShrink: 0 }}>{i + 1}</span>
              <span style={{ whiteSpace: "pre" }}>
                {tokenize(line, p.language).map((token, j) => (
                  <span key={j} style={{ color: COLORS[token.type] }}>{token.text}</span>
                ))}
              </span>
            </div>
          );
        })}
      </pre>
    </div>
  );
};
